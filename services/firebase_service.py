"""
Thin wrapper around Firestore for all persistent state: story config,
characters, episode log, DM disambiguation, and owner-submitted twists.

All Discord snowflake IDs are stored as STRINGS (not ints) to avoid any risk
of precision loss -- Firestore/JSON numbers are doubles, and Discord IDs
regularly exceed the safe integer range for those.

Every public function here is `async def`. firebase-admin's Firestore
client is synchronous under the hood, so each public function offloads its
blocking network I/O to a worker thread via asyncio.to_thread. This matters
a lot in a discord.py bot: a blocking call made directly on the event loop
would stall Discord heartbeats/commands/every other guild for however long
that Firestore round trip takes. The `_sync_*` helpers hold the actual
Firestore calls; callers everywhere else in the codebase just `await` the
public wrapper and never need to think about the threading detail.
"""
import asyncio
import json
from typing import Optional

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter

import config
from services import story_logic

_app = None
_db = None

# Retried on: transient network blips, Firestore briefly unavailable, a
# transaction losing an optimistic-concurrency race (Aborted), and similar
# -- google.api_core.exceptions.{ServiceUnavailable, DeadlineExceeded,
# Aborted, InternalServerError, TooManyRequests} all cover this, but this
# catches Exception broadly rather than enumerating them: missing one of
# those types would silently mean "don't retry when we should", and the
# cost of a broad catch here is small since retries are bounded (a real bug
# still surfaces after 3 attempts, just ~7 seconds later). NOT a substitute
# for local backups against a sustained/extended outage -- see
# services/backup_service.py for that; this only smooths over brief blips.
FIRESTORE_RETRY_ATTEMPTS = 3


async def _run_with_retry(sync_fn, *args):
    last_exc = None
    for attempt in range(FIRESTORE_RETRY_ATTEMPTS):
        try:
            return await asyncio.to_thread(sync_fn, *args)
        except Exception as exc:
            last_exc = exc
            if attempt < FIRESTORE_RETRY_ATTEMPTS - 1:
                print(f"[firebase_service] {sync_fn.__name__} failed (attempt {attempt + 1}/{FIRESTORE_RETRY_ATTEMPTS}): {exc!r} -- retrying")
                await asyncio.sleep(2 ** attempt)
    raise last_exc


def init_firebase():
    """Synchronous by design: called exactly once at process startup,
    before the bot connects to Discord, when there is no concurrent
    event-loop work for a brief blocking call to interfere with."""
    global _app, _db
    if _app is not None:
        return _db
    cred_dict = json.loads(config.FIREBASE_CREDENTIALS_JSON)
    cred = credentials.Certificate(cred_dict)
    _app = firebase_admin.initialize_app(cred)
    _db = firestore.client()
    return _db


def db():
    if _db is None:
        return init_firebase()
    return _db


# ---------- References (cheap local object construction, no I/O) ----------

def story_ref(guild_id: int):
    return db().collection("stories").document(str(guild_id))


def character_ref(guild_id: int, user_id: int):
    return story_ref(guild_id).collection("characters").document(str(user_id))


# ---------- Story config ----------

def _sync_get_story(guild_id: int) -> Optional[dict]:
    snap = story_ref(guild_id).get()
    return snap.to_dict() if snap.exists else None


async def get_story(guild_id: int) -> Optional[dict]:
    return await _run_with_retry(_sync_get_story, guild_id)


def _sync_create_story(guild_id: int, data: dict):
    data = dict(data)
    data["created_at"] = firestore.SERVER_TIMESTAMP
    data["updated_at"] = firestore.SERVER_TIMESTAMP
    story_ref(guild_id).set(data)


async def create_story(guild_id: int, data: dict):
    await _run_with_retry(_sync_create_story, guild_id, data)


def _sync_update_story(guild_id: int, updates: dict):
    updates = dict(updates)
    updates["updated_at"] = firestore.SERVER_TIMESTAMP
    story_ref(guild_id).update(updates)


async def update_story(guild_id: int, updates: dict):
    await _run_with_retry(_sync_update_story, guild_id, updates)


def _sync_list_active_stories() -> list:
    docs = db().collection("stories").where(filter=FieldFilter("status", "==", "active")).stream()
    result = []
    for d in docs:
        item = d.to_dict()
        item["guild_id"] = d.id
        result.append(item)
    return result


async def list_active_stories() -> list:
    return await _run_with_retry(_sync_list_active_stories)


# ---------- Characters ----------

def _sync_get_character(guild_id: int, user_id: int) -> Optional[dict]:
    snap = character_ref(guild_id, user_id).get()
    return snap.to_dict() if snap.exists else None


async def get_character(guild_id: int, user_id: int) -> Optional[dict]:
    return await _run_with_retry(_sync_get_character, guild_id, user_id)


def _sync_upsert_character(guild_id: int, user_id: int, data: dict):
    data = dict(data)
    data["updated_at"] = firestore.SERVER_TIMESTAMP
    character_ref(guild_id, user_id).set(data, merge=True)


async def upsert_character(guild_id: int, user_id: int, data: dict):
    await _run_with_retry(_sync_upsert_character, guild_id, user_id, data)


def _sync_list_characters(guild_id: int) -> list:
    docs = story_ref(guild_id).collection("characters").stream()
    out = []
    for d in docs:
        item = d.to_dict()
        item["user_id"] = d.id
        out.append(item)
    return out


async def list_characters(guild_id: int) -> list:
    return await _run_with_retry(_sync_list_characters, guild_id)


@firestore.transactional
def _claim_unique_character_txn(transaction, guild_id: int, user_id: int, update_fields: dict):
    """
    Atomically checks the new character's label against every OTHER
    currently-alive character in this story, and only if clear, writes the
    record -- all inside one Firestore transaction.

    This closes a real race condition, not just a theoretical one:
    discord.py schedules every incoming Discord event (including on_message
    for DMs) as its own independent asyncio Task, so two DMs from different
    users arriving within the same slice of time are NOT automatically
    serialized -- both handlers can genuinely interleave. A plain
    check-then-write (read the roster, decide there's no king yet, write
    "the king") would let two people claiming the same singular role both
    slip through if their DMs landed close enough together. Doing the read
    and the write inside a single transaction is what prevents that: two
    concurrent transactions attempting to claim the same normalized label
    can't both succeed against Firestore's optimistic-concurrency retries.

    update_fields should NOT include "status" -- this function decides that
    on its own: "alive" for a brand new character, left untouched for an
    update to an existing one, so a player can never un-kill their own
    character just by DMing again.

    Returns the colliding existing character's label (str) if blocked by a
    currently-alive character elsewhere in the roster, else None on success.
    """
    chars_ref = story_ref(guild_id).collection("characters")
    new_label = update_fields.get("display_name", "")
    user_id_str = str(user_id)

    is_new_character = True
    other_characters = []
    # NOTE: transaction.get() only accepts a DocumentReference or a Query --
    # a bare CollectionReference (what chars_ref is) is neither, despite
    # superficially supporting query-like methods; passing it directly
    # raises ValueError at runtime (confirmed the hard way -- this exact
    # line broke every character claim once it started actually running
    # instead of failing earlier in development). CollectionReference.stream()
    # accepts `transaction` directly and is the correct way to do a
    # transactional read of a whole collection.
    for doc in chars_ref.stream(transaction=transaction):
        if doc.id == user_id_str:
            is_new_character = False
            continue
        data = doc.to_dict() or {}
        data["user_id"] = doc.id
        other_characters.append(data)

    living_labels = story_logic.build_living_labels(other_characters)
    collision = story_logic.find_label_collision(new_label, living_labels)
    if collision:
        return collision

    to_write = dict(update_fields)
    to_write["updated_at"] = firestore.SERVER_TIMESTAMP
    if is_new_character:
        to_write["status"] = "alive"

    transaction.set(chars_ref.document(user_id_str), to_write, merge=True)
    return None


def _sync_claim_unique_character(guild_id: int, user_id: int, update_fields: dict):
    transaction = db().transaction()
    return _claim_unique_character_txn(transaction, guild_id, user_id, update_fields)


async def claim_unique_character(guild_id: int, user_id: int, update_fields: dict):
    return await _run_with_retry(_sync_claim_unique_character, guild_id, user_id, update_fields)


# ---------- Episodes (continuity log) ----------

def _sync_append_episode(guild_id: int, episode_number: int, data: dict):
    data = dict(data)
    data["posted_at"] = firestore.SERVER_TIMESTAMP
    story_ref(guild_id).collection("episodes").document(str(episode_number)).set(data)


async def append_episode(guild_id: int, episode_number: int, data: dict):
    await _run_with_retry(_sync_append_episode, guild_id, episode_number, data)


def _sync_get_recent_episodes(guild_id: int, limit: int) -> list:
    # Ordered by posted_at (a timestamp), not by document id -- episode
    # numbers are stored as string doc ids ("2", "10", ...), which would
    # sort lexicographically ("10" before "2") if we ordered by id instead.
    docs = (
        story_ref(guild_id)
        .collection("episodes")
        .order_by("posted_at", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .stream()
    )
    items = [d.to_dict() for d in docs]
    items.reverse()
    return items


async def get_recent_episodes(guild_id: int, limit: int = 3) -> list:
    return await _run_with_retry(_sync_get_recent_episodes, guild_id, limit)


# ---------- Rate limiting (transactional) ----------
# Tracked in its own subcollection, deliberately NOT on the character
# document: a DM can be a pure story suggestion with no character
# information at all, and writing rate-limit state onto a character doc in
# that case would create a malformed "ghost" character (no display_name or
# status) that could then incorrectly appear in the living roster.

def submission_window_ref(guild_id: int, user_id: int):
    return story_ref(guild_id).collection("submission_windows").document(str(user_id))


@firestore.transactional
def _claim_submission_window_txn(transaction, window_ref, next_episode_number):
    snap = window_ref.get(transaction=transaction)
    data = snap.to_dict() if snap.exists else {}
    last = data.get("last_submission_for_episode", -1)
    if last == next_episode_number:
        return False  # this window's single DM slot is already used
    transaction.set(window_ref, {"last_submission_for_episode": next_episode_number}, merge=True)
    return True


def _sync_claim_submission_window(guild_id: int, user_id: int, next_episode_number: int) -> bool:
    transaction = db().transaction()
    ref = submission_window_ref(guild_id, user_id)
    return _claim_submission_window_txn(transaction, ref, next_episode_number)


async def claim_submission_window(guild_id: int, user_id: int, next_episode_number: int) -> bool:
    """Atomically claims this user's one-DM-per-interval slot. Returns True
    if this DM should be processed, False if they've already used this
    window's slot (caller should send the "come back in X" reply)."""
    return await _run_with_retry(_sync_claim_submission_window, guild_id, user_id, next_episode_number)


def _sync_reset_submission_window(guild_id: int, user_id: int):
    submission_window_ref(guild_id, user_id).set({"last_submission_for_episode": -1}, merge=True)


async def reset_submission_window(guild_id: int, user_id: int):
    """Used only when config.ALLOW_RETRY_AFTER_REJECTED_DM is True, to give
    a rejected submission its window slot back."""
    await _run_with_retry(_sync_reset_submission_window, guild_id, user_id)


def _sync_touch_character_submission(guild_id: int, user_id: int, next_episode_number: int):
    try:
        character_ref(guild_id, user_id).update({"last_submission_for_episode": next_episode_number})
    except Exception:
        pass  # no existing character for this user -- nothing to touch, and nothing to create


async def touch_character_submission(guild_id: int, user_id: int, next_episode_number: int):
    """Marks an EXISTING character as freshly active this window (so it's
    prioritized for featuring -- see story_logic.prioritize_cast_candidates)
    without creating a character record if the user doesn't have one yet.
    Used for a suggestion-only DM from someone who already has a character."""
    await _run_with_retry(_sync_touch_character_submission, guild_id, user_id, next_episode_number)


# ---------- DM disambiguation (when a user shares >1 active-story guild with the bot) ----------

def _sync_set_pending_disambiguation(user_id: int, candidate_guild_ids: list, text: str):
    db().collection("dm_disambiguation").document(str(user_id)).set(
        {
            "candidate_guild_ids": candidate_guild_ids,
            "pending_text": text,
            "created_at": firestore.SERVER_TIMESTAMP,
        }
    )


async def set_pending_disambiguation(user_id: int, candidate_guild_ids: list, text: str):
    await _run_with_retry(_sync_set_pending_disambiguation, user_id, candidate_guild_ids, text)


def _sync_get_pending_disambiguation(user_id: int) -> Optional[dict]:
    snap = db().collection("dm_disambiguation").document(str(user_id)).get()
    return snap.to_dict() if snap.exists else None


async def get_pending_disambiguation(user_id: int) -> Optional[dict]:
    return await _run_with_retry(_sync_get_pending_disambiguation, user_id)


def _sync_clear_pending_disambiguation(user_id: int):
    db().collection("dm_disambiguation").document(str(user_id)).delete()


async def clear_pending_disambiguation(user_id: int):
    await _run_with_retry(_sync_clear_pending_disambiguation, user_id)


# ---------- Owner-submitted plot twists ----------

def _sync_add_twist(guild_id: int, text: str):
    story_ref(guild_id).update({"pending_twists": firestore.ArrayUnion([text])})


async def add_twist(guild_id: int, text: str):
    await _run_with_retry(_sync_add_twist, guild_id, text)


def _sync_pop_all_twists(guild_id: int) -> list:
    snap = story_ref(guild_id).get()
    data = snap.to_dict() if snap.exists else {}
    twists = data.get("pending_twists", [])
    if twists:
        story_ref(guild_id).update({"pending_twists": []})
    return twists


async def pop_all_twists(guild_id: int) -> list:
    """Reads and clears all pending twists in one go -- they're meant to be
    consumed by exactly the next episode generated."""
    return await _run_with_retry(_sync_pop_all_twists, guild_id)


# ---------- Player-submitted story suggestions ----------
# Deliberately stored on the STORY document (as a user_id -> text map), not
# on character documents. A suggestion can arrive with no character
# information at all (someone proposing a world event, not a character of
# their own), and writing it onto a character doc in that case would create
# a malformed "ghost" character with no display_name/status that could then
# incorrectly show up in the living roster. Keeping suggestions here avoids
# that entirely. Re-submitting overwrites your own prior pending
# suggestion rather than queuing multiple (rate limiting already prevents
# more than one submission per interval window, so this only ever matters
# across windows, where "replace my last idea with this one" is the
# obviously correct behavior).

def _sync_add_suggestion(guild_id: int, user_id: int, text: str):
    story_ref(guild_id).update({f"pending_suggestions.{user_id}": text})


async def add_suggestion(guild_id: int, user_id: int, text: str):
    await _run_with_retry(_sync_add_suggestion, guild_id, user_id, text)


def _sync_pop_all_suggestions(guild_id: int) -> dict:
    snap = story_ref(guild_id).get()
    data = snap.to_dict() if snap.exists else {}
    suggestions = data.get("pending_suggestions", {}) or {}
    if suggestions:
        story_ref(guild_id).update({"pending_suggestions": {}})
    return suggestions


async def pop_all_suggestions(guild_id: int) -> dict:
    """Reads and clears all pending suggestions (user_id -> text) in one
    go, same consume-once semantics as pop_all_twists."""
    return await _run_with_retry(_sync_pop_all_suggestions, guild_id)
