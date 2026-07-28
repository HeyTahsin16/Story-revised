"""
Core orchestration: turns "it's time for episode N" into a fully generated,
continuity-checked episode, and updates Firestore state accordingly.

Deliberately does NOT touch discord.py directly -- callers (the scheduler
cog) are responsible for actually posting the returned text/image to the
channel. That keeps this module testable and keeps Discord-specific
concerns (embeds, files, channel fetching) out of the narrative logic.
"""
import random

import config
from services import firebase_service as fb
from services import ai_service as ai
from services import story_logic as logic
from data.locations import LOCATIONS, LOCATIONS_BY_KEY


def _pick_new_location(exclude_key):
    candidates = [loc for loc in LOCATIONS if loc["key"] != exclude_key]
    return random.choice(candidates or LOCATIONS)


async def run_episode_1(guild_id: int, story: dict) -> dict:
    """World-building-only opening episode: no dialogue, no characters yet,
    ends with the public 'DM me with your stories.' call to action posted
    separately by the caller once this returns.

    The location itself is NOT chosen here -- /story-setup resolves it
    (owner-picked or AI-picked) at setup time and announces it immediately
    in the onboarding message, so players know what to write characters
    for well before Episode 1 actually posts. The fallback below only
    exists in case of stale/manually-edited Firestore data; it should never
    trigger in normal operation."""
    starting_location_key = (story.get("starting_location_key") or "").strip()
    atmosphere_notes = (story.get("atmosphere_notes") or "").strip()
    location = LOCATIONS_BY_KEY.get(starting_location_key) or random.choice(LOCATIONS)

    episode_text = await ai.generate_episode_1(atmosphere_notes, location["display_name"], location["mood"])

    validation = await ai.validate_episode(
        episode_text=episode_text,
        prior_summary="",
        known_character_statuses={},
        check_no_dialogue=True,
    )

    if validation.get("contains_disallowed_dialogue"):
        # One corrective regeneration attempt -- this is the dual-call
        # architecture doing real work, not just rubber-stamping.
        corrected_notes = atmosphere_notes + "\n(Previous attempt included dialogue -- do not include ANY dialogue this time.)"
        episode_text = await ai.generate_episode_1(corrected_notes, location["display_name"], location["mood"])
        validation = await ai.validate_episode(
            episode_text=episode_text,
            prior_summary="",
            known_character_statuses={},
            check_no_dialogue=True,
        )

    await fb.append_episode(
        guild_id,
        1,
        {
            "content": episode_text,
            "location_key": location["key"],
            "arc_stage": "introduction",
            "featured_user_ids": [],
        },
    )

    return {
        "episode_number": 1,
        "text": episode_text,
        "location": location,
        "featured_user_ids": [],
        "story_summary": validation.get("updated_summary", ""),
    }


async def _gather_cast_candidates(guild_id: int, next_episode_number: int) -> list:
    """Builds the pool of character profiles shown to the AI: everyone who
    submitted fresh content this window is guaranteed a slot ahead of
    anyone just filling space because they haven't been featured recently.
    See story_logic.prioritize_cast_candidates for the (unit-tested)
    ranking rules; this just supplies the live Firestore data."""
    characters = await fb.list_characters(guild_id)
    return logic.prioritize_cast_candidates(characters, next_episode_number, config.CAST_CANDIDATE_POOL_CAP)


async def _gather_suggestions(guild_id: int) -> list:
    """Pops every pending player suggestion (consumed once, like twists) and
    resolves each to the submitter's current character label if they have
    one on file, so the generation prompt can say who's proposing what."""
    raw = await fb.pop_all_suggestions(guild_id)
    if not raw:
        return []
    resolved = []
    for user_id, text in raw.items():
        try:
            character = await fb.get_character(guild_id, int(user_id))
        except (ValueError, TypeError):
            character = None
        resolved.append(
            {
                "user_id": user_id,
                "label": character.get("display_name") if character else None,
                "text": text,
            }
        )
    return resolved


async def run_next_episode(guild_id: int, story: dict) -> dict:
    next_number = story["next_episode_number"]
    total = story["total_episodes"]
    arc_stage = logic.compute_arc_stage(next_number, total)

    scene_length = story.get("scene_length", config.DEFAULT_SCENE_LENGTH_EPISODES)
    scene_started_at = story.get("scene_started_at_episode", 1)
    episodes_into_scene = next_number - scene_started_at
    is_story_finale = next_number >= total
    is_scene_finale = (not is_story_finale) and (episodes_into_scene >= scene_length - 1)

    location = LOCATIONS_BY_KEY.get(story.get("current_location_key"), LOCATIONS[0])

    recent = await fb.get_recent_episodes(guild_id, limit=2)
    recent_text = "\n\n".join(e.get("content", "") for e in recent)

    twists = await fb.pop_all_twists(guild_id)
    suggestions = await _gather_suggestions(guild_id)
    cast_candidates = await _gather_cast_candidates(guild_id, next_number)

    # Fetch each candidate's full record once; reused for both the status
    # context we hand the validator and the ping/alias rules we apply after.
    character_docs = {}
    for c in cast_candidates:
        character_docs[c["user_id"]] = await fb.get_character(guild_id, int(c["user_id"])) or {}

    episode_text = await ai.generate_episode(
        episode_number=next_number,
        total_episodes=total,
        arc_stage=arc_stage,
        location_name=location["display_name"],
        location_mood=location["mood"],
        is_scene_finale=is_scene_finale,
        is_story_finale=is_story_finale,
        story_summary=story.get("story_summary", ""),
        recent_episodes_text=recent_text,
        cast_candidates=cast_candidates,
        twists=twists,
        suggestions=suggestions,
    )

    known_statuses = {uid: doc.get("status", "alive") for uid, doc in character_docs.items()}
    validation = await ai.validate_episode(
        episode_text=episode_text,
        prior_summary=story.get("story_summary", ""),
        known_character_statuses=known_statuses,
        check_no_dialogue=False,
    )

    cast_map = {
        uid: {
            "ping_opt_out": doc.get("ping_opt_out", False),
            "mention_style": doc.get("mention_style", "direct"),
        }
        for uid, doc in character_docs.items()
    }
    final_text = logic.apply_mentions(episode_text, cast_map)
    final_text = logic.strip_unknown_mention_tokens(final_text)

    featured_ids = validation.get("featured_user_ids", [])
    adopted_suggestion_ids = validation.get("adopted_suggestion_user_ids", [])

    await fb.append_episode(
        guild_id,
        next_number,
        {
            "content": final_text,
            "location_key": location["key"],
            "arc_stage": arc_stage,
            "featured_user_ids": featured_ids,
            "adopted_suggestion_user_ids": adopted_suggestion_ids,
        },
    )

    for update in validation.get("character_status_updates", []):
        try:
            await fb.upsert_character(guild_id, int(update["user_id"]), {"status": update["new_status"]})
        except (KeyError, ValueError, TypeError):
            continue

    for uid in featured_ids:
        try:
            await fb.upsert_character(guild_id, int(uid), {"last_featured_episode": next_number})
        except (ValueError, TypeError):
            continue

    next_location_key = location["key"]
    next_scene_started_at = scene_started_at
    if is_scene_finale:
        new_location = _pick_new_location(exclude_key=location["key"])
        next_location_key = new_location["key"]
        next_scene_started_at = next_number + 1

    return {
        "episode_number": next_number,
        "text": final_text,
        "location": location,
        "featured_user_ids": featured_ids,
        "adopted_suggestion_user_ids": adopted_suggestion_ids,
        "story_summary": validation.get("updated_summary", story.get("story_summary", "")),
        "is_story_finale": is_story_finale,
        "next_location_key": next_location_key,
        "next_scene_started_at": next_scene_started_at,
    }
