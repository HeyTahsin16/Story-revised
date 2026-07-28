"""
One-directional local backup of story data, meant to sit on a Railway
Volume (or any mounted persistent directory) as a fallback if Firestore
becomes unreachable for an extended period.

Firebase/Firestore remains the one and only live data store the bot reads
from and writes to during normal operation -- this module never feeds data
back into the bot's decision-making. It's purely an export: periodically
(and on demand via /story-backup), pull everything from Firestore and
write a JSON snapshot to disk. If Firestore ever truly goes down, an owner
has something to inspect or manually recover from; the bot's own behavior
never depends on whether this file exists, is current, or is even
writable, which is what makes this safe to bolt on without turning data
consistency into a two-database problem. See the README's "Local backup"
section for the reasoning behind not doing a live dual-store instead.
"""
import asyncio
import datetime as dt
import json
from pathlib import Path

import config
from services import firebase_service as fb

# get_recent_episodes normally caps small (just enough context for the next
# generation call); a backup wants everything, and the max possible episode
# count (29 days at a 1-hour interval) is comfortably under this.
_MAX_EPISODES_PER_BACKUP = 1000


def _json_default(obj):
    if isinstance(obj, dt.datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def serialize_guild_backup(story: dict, characters: list, episodes: list) -> dict:
    """Pure data shaping -- no I/O -- so it's unit-testable without a live
    Firestore project. Firestore's datetime-like fields are handled by
    _json_default at write time, not here, so this can also be tested with
    plain dicts containing ordinary datetime objects."""
    return {
        "story": story,
        "characters": characters,
        "episodes": episodes,
    }


async def build_full_backup() -> dict:
    """Reads every active story plus its full character roster and episode
    log from Firestore. Returns {guild_id: serialize_guild_backup(...)}."""
    stories = await fb.list_active_stories()
    backup = {}
    for story in stories:
        guild_id = story["guild_id"]
        characters = await fb.list_characters(int(guild_id))
        episodes = await fb.get_recent_episodes(int(guild_id), limit=_MAX_EPISODES_PER_BACKUP)
        backup[guild_id] = serialize_guild_backup(story, characters, episodes)
    return backup


def _sync_write_backup(backup_data: dict) -> str:
    backup_dir = Path(config.LOCAL_BACKUP_DIR)
    backup_dir.mkdir(parents=True, exist_ok=True)

    final_path = backup_dir / "story_backup.json"
    previous_path = backup_dir / "story_backup.previous.json"
    temp_path = backup_dir / "story_backup.json.tmp"

    payload = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "guild_count": len(backup_data),
        "guilds": backup_data,
    }

    # Write to a temp file and rename into place (atomic on POSIX) so a
    # crash mid-write can never leave a half-written, corrupt backup file
    # sitting at the path something might later try to read.
    temp_path.write_text(json.dumps(payload, default=_json_default, indent=2))

    if final_path.exists():
        final_path.replace(previous_path)  # rotate: keep exactly one prior generation
    temp_path.replace(final_path)

    return str(final_path)


async def write_backup_to_disk(backup_data: dict) -> str:
    return await asyncio.to_thread(_sync_write_backup, backup_data)


async def run_backup() -> dict:
    """Orchestrates a full backup: build from Firestore, write to disk.
    Used by both the periodic loop and the manual /story-backup command.
    Never raises -- a backup failure should never take down anything else,
    since this is a nice-to-have safety net, not a load-bearing part of the
    bot's normal operation."""
    if not config.LOCAL_BACKUP_DIR:
        return {"enabled": False}
    try:
        backup_data = await build_full_backup()
        path = await write_backup_to_disk(backup_data)
        return {"enabled": True, "success": True, "path": path, "guild_count": len(backup_data)}
    except Exception as exc:
        print(f"[backup_service] backup failed: {exc!r}")
        return {"enabled": True, "success": False, "error": str(exc)}
