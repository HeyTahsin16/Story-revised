"""
Unit tests for services/backup_service.py's data shaping and JSON
serialization -- the parts that don't require a live Firestore project.
Writing to disk (_sync_write_backup) is exercised with a real temp
directory since that's just local filesystem I/O, not a network call.
"""
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from services import backup_service


def test_serialize_guild_backup_shape():
    story = {"status": "active", "current_episode": 3}
    characters = [{"user_id": "1", "display_name": "the king"}]
    episodes = [{"content": "Episode 1 text"}]
    result = backup_service.serialize_guild_backup(story, characters, episodes)
    assert result == {"story": story, "characters": characters, "episodes": episodes}


def test_json_default_serializes_datetime():
    now = dt.datetime(2026, 1, 1, 12, 0, tzinfo=dt.timezone.utc)
    assert backup_service._json_default(now) == now.isoformat()


def test_json_default_raises_for_unsupported_type():
    class Unserializable:
        pass

    try:
        backup_service._json_default(Unserializable())
        assert False, "should have raised TypeError"
    except TypeError:
        pass


def test_full_backup_payload_round_trips_through_json_with_datetimes():
    # Confirms a realistic Firestore-shaped payload (including datetime
    # fields like next_episode_time/created_at) serializes and reads back
    # correctly end to end -- this is the actual shape write_backup_to_disk
    # will see in production.
    backup_data = {
        "123456789": backup_service.serialize_guild_backup(
            story={
                "status": "active",
                "next_episode_time": dt.datetime(2026, 3, 1, 8, 0, tzinfo=dt.timezone.utc),
                "created_at": dt.datetime(2026, 2, 1, 0, 0, tzinfo=dt.timezone.utc),
            },
            characters=[{"user_id": "1", "display_name": "the king", "status": "alive"}],
            episodes=[{"content": "Once upon a time...", "posted_at": dt.datetime(2026, 2, 1, 3, 0, tzinfo=dt.timezone.utc)}],
        )
    }
    serialized = json.dumps(backup_data, default=backup_service._json_default)
    reloaded = json.loads(serialized)
    assert reloaded["123456789"]["story"]["status"] == "active"
    assert reloaded["123456789"]["story"]["next_episode_time"] == "2026-03-01T08:00:00+00:00"
    assert reloaded["123456789"]["characters"][0]["display_name"] == "the king"
    assert reloaded["123456789"]["episodes"][0]["content"] == "Once upon a time..."


def test_write_backup_to_disk_creates_file_and_rotates_previous(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LOCAL_BACKUP_DIR", str(tmp_path))

    first_payload = {"g1": backup_service.serialize_guild_backup({"status": "active"}, [], [])}
    path1 = backup_service._sync_write_backup(first_payload)
    assert Path(path1).exists()
    with open(path1) as f:
        data1 = json.load(f)
    assert data1["guild_count"] == 1

    # Writing a second time should rotate the first into .previous.json
    # rather than just silently vanishing.
    second_payload = {"g1": backup_service.serialize_guild_backup({"status": "active"}, [], []),
                       "g2": backup_service.serialize_guild_backup({"status": "active"}, [], [])}
    path2 = backup_service._sync_write_backup(second_payload)
    assert path1 == path2  # same "latest" filename each time
    previous_path = tmp_path / "story_backup.previous.json"
    assert previous_path.exists()
    with open(previous_path) as f:
        previous_data = json.load(f)
    assert previous_data["guild_count"] == 1  # the FIRST payload, now rotated back

    with open(path2) as f:
        latest_data = json.load(f)
    assert latest_data["guild_count"] == 2  # the SECOND payload is now "latest"


def test_write_backup_creates_directory_if_missing(tmp_path, monkeypatch):
    nested_dir = tmp_path / "does" / "not" / "exist" / "yet"
    monkeypatch.setattr(config, "LOCAL_BACKUP_DIR", str(nested_dir))
    path = backup_service._sync_write_backup({"g1": backup_service.serialize_guild_backup({}, [], [])})
    assert Path(path).exists()
