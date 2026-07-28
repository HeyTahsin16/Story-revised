"""
Pure, dependency-free narrative logic: episode-count math, arc pacing,
mention-token substitution, rate-limit windows, and JIT scheduling checks.

Deliberately has zero imports of discord/firebase/anthropic so it can be
unit tested in isolation (see tests/test_story_logic.py) without touching
any external service or credential.
"""
import datetime as dt
import json
import random
import re

import config

MENTION_TOKEN_RE = re.compile(r"<<MENTION:(\d+)>>")


def compute_total_episodes(interval_hours: int, duration_days: int) -> int:
    """E.g. a 1-day interval over 10 days = 10 episodes; a 6-hour interval
    over 10 days = 40 episodes (both are the spec's own worked examples)."""
    total_hours = duration_days * 24
    episodes = total_hours // interval_hours
    return max(1, int(episodes))


def compute_arc_stage(next_episode_number: int, total_episodes: int) -> str:
    """Buckets the upcoming episode into introduction / rising_action /
    climax / resolution based on how far through the story it falls, so the
    final episode always lands in "resolution" no matter the story length."""
    if total_episodes <= 1 or next_episode_number >= total_episodes:
        return "resolution"
    progress = next_episode_number / total_episodes
    if progress <= config.ARC_INTRODUCTION_END:
        return "introduction"
    if progress <= config.ARC_RISING_ACTION_END:
        return "rising_action"
    if progress <= config.ARC_CLIMAX_END:
        return "climax"
    return "resolution"


def compute_time_remaining_string(target: dt.datetime, now: dt.datetime) -> str:
    """Used for the "Come back in X hours, X minutes" rate-limit reply."""
    delta = target - now
    total_seconds = max(0, int(delta.total_seconds()))
    hours, remainder = divmod(total_seconds, 3600)
    minutes = remainder // 60
    if hours and minutes:
        return f"{hours} hour{'s' if hours != 1 else ''}, {minutes} minute{'s' if minutes != 1 else ''}"
    if hours:
        return f"{hours} hour{'s' if hours != 1 else ''}"
    if minutes:
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    return "a moment"


def is_within_jit_window(next_episode_time: dt.datetime, now: dt.datetime, max_minutes: int) -> bool:
    """True once we're within max_minutes of the scheduled post time --
    including "overdue" (negative minutes away), which is what lets the
    scheduler catch up cleanly after a container restart. Never returns
    True more than max_minutes early, satisfying "must never pre-generate
    the story early"."""
    minutes_away = (next_episode_time - now).total_seconds() / 60
    return minutes_away <= max_minutes


def apply_mentions(text: str, cast: dict) -> str:
    """
    Replace AI-emitted "<<MENTION:user_id>>" placeholder tokens with the
    correctly formatted Discord mention -- or with nothing at all for a
    user who opted out of pings. This enforces ping opt-outs and the
    "never ping NPCs" rule deterministically in code, rather than trusting
    the model to remember and apply those rules itself every time.

    cast: dict of user_id (str) -> {"ping_opt_out": bool, "mention_style": "direct"|"alias"}
    Tokens for ids not present in `cast` are stripped defensively (never
    fabricate a mention for someone we don't have consent/style info for).

    Expected input shape from the model, e.g.:
        "Doctor<<MENTION:123>> was pacing the room."
    becomes (direct, not opted out):
        "Doctor <@123> was pacing the room."
    becomes (alias, not opted out):
        "Doctor (<@123>) was pacing the room."
    becomes (opted out):
        "Doctor was pacing the room."
    """
    def _replace(match: "re.Match") -> str:
        user_id = match.group(1)
        info = cast.get(user_id)
        if info is None:
            return ""
        if info.get("ping_opt_out"):
            return ""
        if info.get("mention_style") == "alias":
            return f" (<@{user_id}>)"
        return f" <@{user_id}>"

    replaced = MENTION_TOKEN_RE.sub(_replace, text)
    replaced = re.sub(r"[ \t]{2,}", " ", replaced)
    replaced = re.sub(r" +([.,!?])", r"\1", replaced)
    return replaced


def strip_unknown_mention_tokens(text: str) -> str:
    """Safety net: remove any leftover mention tokens that apply_mentions
    didn't already clean up (shouldn't normally happen, but a stray token
    reaching Discord would look broken)."""
    return MENTION_TOKEN_RE.sub("", text)


_LEADING_ARTICLE_RE = re.compile(r"^(the|a|an)\s+")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_character_label(label: str) -> str:
    """Case/whitespace/article-insensitive normalization so "the King",
    "King", "a king", and "KING " are all recognized as the same claim."""
    normalized = (label or "").strip().lower()
    normalized = _LEADING_ARTICLE_RE.sub("", normalized)
    normalized = _WHITESPACE_RE.sub(" ", normalized).strip()
    return normalized


def find_label_collision(new_label: str, existing_labels: list) -> str:
    """
    Deterministic, code-guaranteed check for an exact/near-exact literal
    duplicate identity claim -- e.g. two people both submitting "I'm the
    king" and "im the king too". This is the first, unconditional line of
    defense against the "multiple users claim the same unique role"
    problem: it does not depend on any AI judgment call, so it's fully
    unit-testable and holds regardless of which AI provider is configured.

    A second, AI-driven semantic check (services/ai_service.classify_submission)
    additionally tries to catch paraphrased duplicates ("I rule this
    kingdom" vs "I am the king") that this literal check would miss, but
    that check's reliability depends on the model.

    Returns the colliding existing label if found, else None. Checking
    against every existing label (not just the most recent one) is what
    makes this correct for 3+ simultaneous claimants, not just 2: the
    second AND third person to submit "the king" both collide with the
    first successful claim, because both are checked against the same
    current roster, not against each other.
    """
    new_norm = normalize_character_label(new_label)
    if not new_norm:
        return None
    for existing in existing_labels:
        if normalize_character_label(existing) == new_norm:
            return existing
    return None


def build_living_labels(characters: list, exclude_user_id: str = None) -> list:
    """
    Given raw character records (dicts with "user_id", "display_name",
    "status"), returns the display_name of everyone currently alive or
    revived -- excluding a given user id (so someone editing their own
    existing character never "collides" with themselves) and excluding
    anyone deceased.

    Excluding the deceased is what makes succession work automatically: if
    the current "king" character dies (the AI validator marks them
    deceased), their label simply stops appearing in this list, so the
    next claimant to "the king" is correctly treated as taking a now-vacant
    role rather than blocked as a duplicate.
    """
    return [
        c.get("display_name", "")
        for c in characters
        if c.get("status") != "deceased" and c.get("user_id") != exclude_user_id
    ]


def truncate_suggestion(text: str, max_length: int = 400) -> str:
    """
    Defense-in-depth cap on player-submitted story suggestions, independent
    of the AI's own judgment call on whether a suggestion is reasonable.
    A single proposed event or character choice fits comfortably under this
    limit; something long enough to effectively be a ghostwritten episode
    (or the "story" itself) does not, and gets cut off rather than handed
    to the author wholesale. This runs regardless of AI provider.
    """
    text = (text or "").strip()
    if len(text) <= max_length:
        return text
    return text[:max_length].rstrip() + "..."


def parse_admin_ids(raw: str) -> set:
    """
    Parses BOT_ADMIN_USER_IDS ("111111111111111111,222222222222222222")
    into a set of ints. Blank/malformed entries are silently skipped rather
    than crashing startup over a stray comma or typo.
    """
    return {int(piece.strip()) for piece in (raw or "").split(",") if piece.strip().isdigit()}


def prioritize_cast_candidates(characters: list, next_episode_number: int, cap: int) -> list:
    """
    Builds the ranked pool of character profiles offered to the AI for a
    given episode. Everyone who submitted something fresh this window
    (a character update and/or a story suggestion both set
    last_submission_for_episode) is guaranteed a slot ahead of anyone only
    filling space because they haven't been featured recently -- so a
    fresh suggestion never gets crowded out of the prompt by an unrelated
    shuffle when a cap is in play. Deceased characters are always excluded.
    """
    fresh, filler = [], []
    for c in characters:
        if c.get("status") == "deceased":
            continue
        entry = {
            "user_id": c.get("user_id", ""),
            "label": c.get("display_name", "a character"),
            "backstory": c.get("backstory", ""),
        }
        is_fresh = c.get("last_submission_for_episode") in (next_episode_number - 1, next_episode_number)
        recently_featured = c.get("last_featured_episode", -999) >= next_episode_number - 2
        if is_fresh:
            fresh.append(entry)
        elif not recently_featured:
            filler.append(entry)
    random.shuffle(fresh)
    random.shuffle(filler)
    return (fresh + filler)[:cap]


_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


def _try_parse(candidate: str) -> dict:
    """Tries a candidate JSON string as-is, then again with trailing commas
    before a closing brace/bracket stripped (e.g. {"a": 1,} or [1, 2,]) --
    a very common small mistake models make that's otherwise a total
    parse failure despite the content being unambiguous. Raises
    json.JSONDecodeError if neither works, matching json.loads's own
    contract so callers can keep using the same except clause."""
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass
    cleaned = re.sub(r",(\s*[\}\]])", r"\1", candidate)
    return json.loads(cleaned)


def extract_json(text: str) -> dict:
    """
    Parses a JSON object out of raw model output, tolerating the common
    ways models wrap or surround it even when explicitly told not to:
    markdown code fences (with or without a "json" tag), a preamble
    sentence before the fence, a remark after it, trailing commas, or no
    fence at all with the JSON just embedded in some other text. This
    directly matters for reliability: a single confirmed real-world
    failure was a DM being rejected with a generic "something went wrong"
    error on every attempt, traced to the old strict version of this
    function only handling a perfectly bare or perfectly fenced response
    and giving up on anything else (a very common way for models --
    especially smaller/faster ones used for classification -- to actually
    format output despite instructions).

    Tries, in order: (1) the whole trimmed string, (2) a fenced
    ```json ... ``` block found anywhere in the text, (3) the substring
    between the first "{" and the last "}" in the text -- each with and
    without trailing-comma cleanup. Raises ValueError if none of these
    parse, so callers can fall back to a safe default exactly as before.
    """
    text = (text or "").strip()

    try:
        return _try_parse(text)
    except json.JSONDecodeError:
        pass

    fence_match = _FENCED_JSON_RE.search(text)
    if fence_match:
        try:
            return _try_parse(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        try:
            return _try_parse(text[first_brace : last_brace + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not extract JSON from model output: {text[:200]!r}")


def compute_generation_backoff_minutes(consecutive_failures: int, max_minutes: int = 60) -> int:
    """
    Exponential backoff for how long to wait before retrying a guild whose
    last episode-generation attempt failed, so a persistent failure (an
    exhausted daily AI provider quota, a bad API key, a sustained outage)
    doesn't get hammered every single scheduler tick indefinitely. This is
    not a hypothetical concern: a free-tier AI quota of just 20 requests/day
    was measured being exhausted within minutes purely from a failing guild
    being retried every 60 seconds with no backoff at all. Doubles each
    failure, capped at max_minutes. Expects consecutive_failures >= 1 (call
    after incrementing the failure count, not before).
    """
    consecutive_failures = max(consecutive_failures, 1)
    return min(2 ** consecutive_failures, max_minutes)


def split_into_chunks(text: str, limit: int) -> list:
    """
    Splits episode text into pieces that each fit under `limit` characters,
    breaking at paragraph boundaries (blank lines) so a chunk boundary
    never lands mid-sentence. Needed once episode length targets went up
    (6-10 paragraphs) enough that a single episode could plausibly exceed
    Discord's 4096-char embed description limit -- silently truncating an
    episode mid-thought is worse than posting it as two or three messages.

    A single paragraph that's on its own longer than `limit` (unusual, but
    not impossible) still gets hard-split rather than silently dropped.
    """
    text = (text or "").strip()
    if len(text) <= limit:
        return [text] if text else []

    paragraphs = text.split("\n\n")
    chunks = []
    current = ""
    for para in paragraphs:
        candidate = f"{current}\n\n{para}" if current else para
        if len(candidate) > limit and current:
            chunks.append(current)
            current = para
        else:
            current = candidate
    if current:
        chunks.append(current)

    final_chunks = []
    for chunk in chunks:
        while len(chunk) > limit:
            final_chunks.append(chunk[:limit])
            chunk = chunk[limit:]
        if chunk:
            final_chunks.append(chunk)
    return final_chunks
