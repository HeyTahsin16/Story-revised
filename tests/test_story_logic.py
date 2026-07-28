"""
Unit tests for services/story_logic.py -- the only module with zero
external dependencies, so the only one testable without live Discord/
Firebase/Anthropic credentials. Run with: pytest tests/
"""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from services import story_logic as logic


# ---------- compute_total_episodes ----------

def test_total_episodes_matches_spec_example_1():
    # "a 1-day interval over 10 days = 10 episodes"
    assert logic.compute_total_episodes(interval_hours=24, duration_days=10) == 10


def test_total_episodes_matches_spec_example_2():
    # "a 6-hour interval over 10 days = 40 episodes"
    assert logic.compute_total_episodes(interval_hours=6, duration_days=10) == 40


def test_total_episodes_floors_uneven_division():
    assert logic.compute_total_episodes(interval_hours=5, duration_days=1) == 4  # 24 // 5 = 4


def test_total_episodes_minimum_one():
    assert logic.compute_total_episodes(interval_hours=24, duration_days=1) == 1


# ---------- compute_arc_stage ----------

def test_arc_stage_introduction_at_start():
    assert logic.compute_arc_stage(1, 100) == "introduction"


def test_arc_stage_rising_action_midpoint():
    assert logic.compute_arc_stage(50, 100) == "rising_action"


def test_arc_stage_climax_near_end():
    # 85/100 = 85% progress, inside the (70%, 90%] climax band.
    assert logic.compute_arc_stage(85, 100) == "climax"


def test_arc_stage_resolution_past_climax_threshold():
    # 92/100 = 92% progress, past the 90% climax cutoff -> resolution.
    assert logic.compute_arc_stage(92, 100) == "resolution"


def test_arc_stage_resolution_on_final_episode():
    assert logic.compute_arc_stage(100, 100) == "resolution"


def test_arc_stage_resolution_when_only_one_episode_total():
    assert logic.compute_arc_stage(1, 1) == "resolution"


def test_arc_stage_never_skips_resolution_for_short_stories():
    # A 10-episode story should still land cleanly on resolution at the end.
    assert logic.compute_arc_stage(10, 10) == "resolution"
    assert logic.compute_arc_stage(1, 10) == "introduction"


# ---------- compute_time_remaining_string ----------

def test_time_remaining_hours_and_minutes():
    now = dt.datetime(2026, 1, 1, 0, 0, tzinfo=dt.timezone.utc)
    target = now + dt.timedelta(hours=2, minutes=15)
    assert logic.compute_time_remaining_string(target, now) == "2 hours, 15 minutes"


def test_time_remaining_singular_hour_and_minute():
    now = dt.datetime(2026, 1, 1, 0, 0, tzinfo=dt.timezone.utc)
    target = now + dt.timedelta(hours=1, minutes=1)
    assert logic.compute_time_remaining_string(target, now) == "1 hour, 1 minute"


def test_time_remaining_minutes_only():
    now = dt.datetime(2026, 1, 1, 0, 0, tzinfo=dt.timezone.utc)
    target = now + dt.timedelta(minutes=45)
    assert logic.compute_time_remaining_string(target, now) == "45 minutes"


def test_time_remaining_never_negative():
    now = dt.datetime(2026, 1, 1, 0, 0, tzinfo=dt.timezone.utc)
    target = now - dt.timedelta(minutes=10)  # already overdue
    assert logic.compute_time_remaining_string(target, now) == "a moment"


# ---------- is_within_jit_window ----------

def test_jit_window_too_early_returns_false():
    now = dt.datetime(2026, 1, 1, 0, 0, tzinfo=dt.timezone.utc)
    target = now + dt.timedelta(minutes=10)  # 10 min away, window is 5
    assert logic.is_within_jit_window(target, now, max_minutes=5) is False


def test_jit_window_within_range_returns_true():
    now = dt.datetime(2026, 1, 1, 0, 0, tzinfo=dt.timezone.utc)
    target = now + dt.timedelta(minutes=3)
    assert logic.is_within_jit_window(target, now, max_minutes=5) is True


def test_jit_window_overdue_still_triggers_for_catchup():
    now = dt.datetime(2026, 1, 1, 0, 0, tzinfo=dt.timezone.utc)
    target = now - dt.timedelta(minutes=30)  # bot was down, we're overdue
    assert logic.is_within_jit_window(target, now, max_minutes=5) is True


# ---------- apply_mentions ----------

def test_apply_mentions_direct_style():
    text = "Doctor<<MENTION:123>> was pacing the room."
    cast = {"123": {"ping_opt_out": False, "mention_style": "direct"}}
    assert logic.apply_mentions(text, cast) == "Doctor <@123> was pacing the room."


def test_apply_mentions_alias_style():
    text = "Beelzebub<<MENTION:456>> was sleeping that night."
    cast = {"456": {"ping_opt_out": False, "mention_style": "alias"}}
    assert logic.apply_mentions(text, cast) == "Beelzebub (<@456>) was sleeping that night."


def test_apply_mentions_respects_opt_out():
    text = "Doctor<<MENTION:123>> was pacing the room."
    cast = {"123": {"ping_opt_out": True, "mention_style": "direct"}}
    assert logic.apply_mentions(text, cast) == "Doctor was pacing the room."


def test_apply_mentions_strips_unknown_ids():
    # Never fabricate a mention for an id we have no consent/style record for.
    text = "A stranger<<MENTION:999>> watched from the doorway."
    cast = {}
    assert "<@999>" not in logic.apply_mentions(text, cast)
    assert "<<MENTION" not in logic.apply_mentions(text, cast)


def test_apply_mentions_multiple_characters_in_one_episode():
    text = "Doctor<<MENTION:1>> nodded at Beelzebub<<MENTION:2>>."
    cast = {
        "1": {"ping_opt_out": False, "mention_style": "direct"},
        "2": {"ping_opt_out": False, "mention_style": "alias"},
    }
    assert logic.apply_mentions(text, cast) == "Doctor <@1> nodded at Beelzebub (<@2>)."


def test_strip_unknown_mention_tokens():
    text = "Someone<<MENTION:42>> lingered."
    assert logic.strip_unknown_mention_tokens(text) == "Someone lingered."


# ---------- normalize_character_label / find_label_collision ----------
# These cover the "two users both claim to be the king" problem from a pure,
# deterministic, code-guaranteed angle (a second, AI-driven semantic check
# also exists in ai_service.classify_submission, but that one isn't
# testable without a live model call -- this deterministic layer is, and it
# alone already handles the literal scenario described: identical or
# near-identical claims, regardless of how many people make them).

def test_normalize_strips_articles_case_and_whitespace():
    assert logic.normalize_character_label("The King") == "king"
    assert logic.normalize_character_label("a king") == "king"
    assert logic.normalize_character_label("  KING  ") == "king"
    assert logic.normalize_character_label("king") == "king"


def test_find_label_collision_detects_exact_duplicate():
    assert logic.find_label_collision("the king", ["the king"]) == "the king"


def test_find_label_collision_detects_case_and_article_variants():
    # "im the king" (user 2) vs "the King" (user 1, already claimed)
    assert logic.find_label_collision("King", ["the King"]) == "the King"
    assert logic.find_label_collision("a King", ["the king"]) == "the king"


def test_find_label_collision_scales_to_three_or_more_claimants():
    # The exact worry raised: "that wont solve 3 users submitting king tho."
    # Checking against the FULL current roster (not just the prior user)
    # means every subsequent claimant collides with the same first holder,
    # regardless of how many have already tried.
    existing_roster = ["the king"]  # user 1 already successfully claimed this
    assert logic.find_label_collision("the king", existing_roster) == "the king"  # user 2 blocked
    assert logic.find_label_collision("King", existing_roster) == "the king"       # user 3 blocked too
    assert logic.find_label_collision("a king", existing_roster) == "the king"     # user 4 blocked too


def test_find_label_collision_no_false_positive_for_distinct_roles():
    assert logic.find_label_collision("a soldier", ["the king", "a merchant"]) is None
    assert logic.find_label_collision("the queen", ["the king"]) is None


def test_find_label_collision_empty_roster_never_collides():
    assert logic.find_label_collision("the king", []) is None


def test_find_label_collision_empty_label_never_collides():
    # Guards against a blank/failed extraction being treated as matching everything.
    assert logic.find_label_collision("", ["the king"]) is None


# ---------- build_living_labels (excludes self + the deceased) ----------

def test_build_living_labels_excludes_self():
    characters = [
        {"user_id": "1", "display_name": "the king", "status": "alive"},
        {"user_id": "2", "display_name": "a soldier", "status": "alive"},
    ]
    labels = logic.build_living_labels(characters, exclude_user_id="1")
    assert "the king" not in labels
    assert "a soldier" in labels


def test_build_living_labels_excludes_deceased():
    characters = [
        {"user_id": "1", "display_name": "the king", "status": "deceased"},
        {"user_id": "2", "display_name": "a soldier", "status": "alive"},
    ]
    labels = logic.build_living_labels(characters)
    assert "the king" not in labels
    assert "a soldier" in labels


def test_succession_scenario_throne_reopens_after_death():
    # The exact "one king dies, the next king is another user" idea the
    # request raised -- confirms it falls out of the design for free: once
    # the first king is marked deceased, they no longer appear in the
    # living-labels list, so a new "the king" claim no longer collides.
    characters = [{"user_id": "1", "display_name": "the king", "status": "deceased"}]
    living_labels = logic.build_living_labels(characters, exclude_user_id="2")
    assert logic.find_label_collision("the king", living_labels) is None

    # But while that same king is still alive, a second claimant IS blocked.
    characters_alive = [{"user_id": "1", "display_name": "the king", "status": "alive"}]
    living_labels_alive = logic.build_living_labels(characters_alive, exclude_user_id="2")
    assert logic.find_label_collision("the king", living_labels_alive) == "the king"


# ---------- truncate_suggestion ----------

def test_truncate_suggestion_leaves_short_text_untouched():
    assert logic.truncate_suggestion("kill the villain", max_length=400) == "kill the villain"


def test_truncate_suggestion_cuts_long_text():
    long_text = "a" * 1000
    result = logic.truncate_suggestion(long_text, max_length=400)
    assert len(result) <= 404  # 400 chars + "..."
    assert result.endswith("...")


def test_truncate_suggestion_strips_whitespace():
    assert logic.truncate_suggestion("  hello  ", max_length=400) == "hello"


def test_truncate_suggestion_handles_empty():
    assert logic.truncate_suggestion("", max_length=400) == ""
    assert logic.truncate_suggestion(None, max_length=400) == ""


# ---------- parse_admin_ids ----------

def test_parse_admin_ids_single():
    assert logic.parse_admin_ids("123456789012345678") == {123456789012345678}


def test_parse_admin_ids_multiple_with_whitespace():
    assert logic.parse_admin_ids("111, 222 ,333") == {111, 222, 333}


def test_parse_admin_ids_skips_junk():
    assert logic.parse_admin_ids("111,abc,,222") == {111, 222}


def test_parse_admin_ids_empty_string():
    assert logic.parse_admin_ids("") == set()
    assert logic.parse_admin_ids(None) == set()


# ---------- prioritize_cast_candidates ----------

def test_prioritize_excludes_deceased():
    characters = [
        {"user_id": "1", "display_name": "dead guy", "status": "deceased", "last_submission_for_episode": 5},
        {"user_id": "2", "display_name": "alive guy", "status": "alive", "last_submission_for_episode": 5},
    ]
    result = logic.prioritize_cast_candidates(characters, next_episode_number=5, cap=10)
    labels = [c["label"] for c in result]
    assert "dead guy" not in labels
    assert "alive guy" in labels


def test_prioritize_fresh_submissions_always_beat_the_cap():
    # 20 fresh submissions, cap of 5 -- every slot should go to a fresh
    # submitter, never to filler, so a suggestion never gets crowded out.
    fresh_characters = [
        {
            "user_id": str(i),
            "display_name": f"fresh {i}",
            "status": "alive",
            "last_submission_for_episode": 10,
        }
        for i in range(20)
    ]
    filler_characters = [
        {
            "user_id": f"filler-{i}",
            "display_name": f"filler {i}",
            "status": "alive",
            "last_submission_for_episode": 1,
            "last_featured_episode": 1,
        }
        for i in range(5)
    ]
    result = logic.prioritize_cast_candidates(fresh_characters + filler_characters, next_episode_number=10, cap=5)
    assert len(result) == 5
    assert all(c["label"].startswith("fresh") for c in result)


def test_prioritize_fills_remaining_slots_with_non_recently_featured():
    characters = [
        {"user_id": "1", "display_name": "not recent", "status": "alive", "last_submission_for_episode": 1, "last_featured_episode": 1},
    ]
    result = logic.prioritize_cast_candidates(characters, next_episode_number=10, cap=5)
    assert len(result) == 1
    assert result[0]["label"] == "not recent"


def test_prioritize_excludes_recently_featured_non_fresh_characters():
    characters = [
        {"user_id": "1", "display_name": "just featured", "status": "alive", "last_submission_for_episode": 1, "last_featured_episode": 9},
    ]
    result = logic.prioritize_cast_candidates(characters, next_episode_number=10, cap=5)
    assert result == []


def test_prioritize_respects_cap():
    characters = [
        {"user_id": str(i), "display_name": f"char {i}", "status": "alive", "last_submission_for_episode": 10}
        for i in range(30)
    ]
    result = logic.prioritize_cast_candidates(characters, next_episode_number=10, cap=15)
    assert len(result) == 15


# ---------- extract_json ----------
# The old strict version of this only handled a perfectly bare JSON string
# or a JSON string fenced with NOTHING else around it. In real usage, this
# reliably broke DM processing: every submission came back "something went
# wrong reading that submission" because the model (Claude Haiku, the
# default fast-tier classifier) wrapped its output in ways the old
# start/end-anchored regex didn't handle. These tests cover every such
# shape found or plausible in practice.

def test_extract_json_bare():
    assert logic.extract_json('{"is_valid": true}') == {"is_valid": True}


def test_extract_json_clean_fence():
    text = '```json\n{"is_valid": true}\n```'
    assert logic.extract_json(text) == {"is_valid": True}


def test_extract_json_fence_without_json_tag():
    text = '```\n{"is_valid": true}\n```'
    assert logic.extract_json(text) == {"is_valid": True}


def test_extract_json_fence_with_leading_preamble():
    # A model adding an explanatory sentence before the fence despite being
    # told not to -- this is the shape that broke the old anchored regex,
    # since it only matched a fence at the very start of the string.
    text = 'Sure, here is my evaluation:\n\n```json\n{"is_valid": true}\n```'
    assert logic.extract_json(text) == {"is_valid": True}


def test_extract_json_fence_with_trailing_remark():
    text = '```json\n{"is_valid": true}\n```\n\nLet me know if you need anything else!'
    assert logic.extract_json(text) == {"is_valid": True}


def test_extract_json_fence_with_preamble_and_trailing_remark():
    text = 'Here you go:\n```json\n{"is_valid": true, "character_label": "Mara"}\n```\nHope that helps.'
    assert logic.extract_json(text) == {"is_valid": True, "character_label": "Mara"}


def test_extract_json_no_fence_embedded_in_prose():
    text = 'The result is {"is_valid": true} based on the submission.'
    assert logic.extract_json(text) == {"is_valid": True}


def test_extract_json_uppercase_json_tag():
    text = '```JSON\n{"is_valid": false}\n```'
    assert logic.extract_json(text) == {"is_valid": False}


def test_extract_json_multiline_object():
    text = '```json\n{\n  "is_valid": true,\n  "character_label": "the doctor"\n}\n```'
    assert logic.extract_json(text) == {"is_valid": True, "character_label": "the doctor"}


def test_extract_json_raises_on_genuinely_unparseable_text():
    with pytest.raises(ValueError):
        logic.extract_json("I couldn't process that request at all.")


def test_extract_json_raises_on_empty_string():
    with pytest.raises(ValueError):
        logic.extract_json("")


def test_extract_json_trailing_comma_in_object():
    text = '{"is_valid": true, "character_label": "Mara",}'
    assert logic.extract_json(text) == {"is_valid": True, "character_label": "Mara"}


def test_extract_json_trailing_comma_in_nested_array():
    text = '{"featured_user_ids": ["1", "2",]}'
    assert logic.extract_json(text) == {"featured_user_ids": ["1", "2"]}


def test_extract_json_trailing_comma_inside_fence_with_preamble():
    # Combines every real-world quirk found at once: preamble + fence + trailing comma.
    text = 'Here is the result:\n```json\n{"is_valid": true, "tags": ["a", "b",],}\n```'
    assert logic.extract_json(text) == {"is_valid": True, "tags": ["a", "b"]}


# ---------- split_into_chunks ----------

def test_split_short_text_returns_single_chunk():
    text = "One short paragraph."
    assert logic.split_into_chunks(text, limit=4000) == [text]


def test_split_empty_text_returns_empty_list():
    assert logic.split_into_chunks("", limit=4000) == []


def test_split_breaks_at_paragraph_boundaries():
    paragraphs = ["Paragraph one." * 20, "Paragraph two." * 20, "Paragraph three." * 20]
    text = "\n\n".join(paragraphs)
    chunks = logic.split_into_chunks(text, limit=len(paragraphs[0]) + len(paragraphs[1]) + 10)
    # Should split so paragraph three lands in its own chunk rather than
    # exceeding the limit crammed in with the first two.
    assert len(chunks) >= 2
    assert all(len(c) <= len(paragraphs[0]) + len(paragraphs[1]) + 10 for c in chunks)


def test_split_never_exceeds_limit_even_for_a_single_oversized_paragraph():
    text = "x" * 10000  # one giant "paragraph" with no blank-line breaks at all
    chunks = logic.split_into_chunks(text, limit=4000)
    assert all(len(c) <= 4000 for c in chunks)
    assert "".join(chunks) == text  # nothing silently dropped


def test_split_reassembles_to_original_content():
    paragraphs = [f"Paragraph {i} with some words in it." * 5 for i in range(10)]
    text = "\n\n".join(paragraphs)
    chunks = logic.split_into_chunks(text, limit=300)
    # Every paragraph's text should appear somewhere across the chunks --
    # confirms the splitter isn't dropping content anywhere.
    rejoined = "\n\n".join(chunks)
    for para in paragraphs:
        assert para in rejoined


def test_split_respects_limit_exactly_at_boundary():
    text = "a" * 4000
    assert logic.split_into_chunks(text, limit=4000) == [text]
    text_over = "a" * 4001
    chunks = logic.split_into_chunks(text_over, limit=4000)
    assert len(chunks) == 2
    assert all(len(c) <= 4000 for c in chunks)


# ---------- compute_generation_backoff_minutes ----------

def test_backoff_doubles_each_failure():
    assert logic.compute_generation_backoff_minutes(1, max_minutes=1000) == 2
    assert logic.compute_generation_backoff_minutes(2, max_minutes=1000) == 4
    assert logic.compute_generation_backoff_minutes(3, max_minutes=1000) == 8
    assert logic.compute_generation_backoff_minutes(4, max_minutes=1000) == 16


def test_backoff_caps_at_max_minutes():
    assert logic.compute_generation_backoff_minutes(10, max_minutes=60) == 60
    assert logic.compute_generation_backoff_minutes(100, max_minutes=60) == 60


def test_backoff_treats_zero_or_negative_as_first_failure():
    assert logic.compute_generation_backoff_minutes(0, max_minutes=1000) == 2
    assert logic.compute_generation_backoff_minutes(-5, max_minutes=1000) == 2
