"""
Central configuration for the storytelling bot.

Loads secrets/config from environment variables (via .env locally, or the
platform's env var settings on Railway) and exposes tunable constants used
throughout the codebase. Nothing in this module performs network I/O or
raises on import -- validate_config() is called explicitly at startup so
that importing this module (e.g. from unit tests) is always safe.
"""
import os

from dotenv import load_dotenv

load_dotenv()

VERSION = "1.6.0"

# --- Required secrets / credentials ---
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
# Discord user id(s) that count as an "owner" for /story-* commands on ANY
# server the bot is in, in addition to that server's actual owner -- lets
# the bot's operator manage/test across servers they don't personally own.
# Comma-separated if more than one, e.g. "111111111111111111,222222222222222222".
# Kept as a raw string here (not parsed into a set) so config.py doesn't
# need to import services.story_logic, which itself imports config --
# see cogs/checks.py for where this actually gets parsed and used.
BOT_ADMIN_USER_IDS_RAW = os.environ.get("BOT_ADMIN_USER_IDS", "")
# The full Firebase service account JSON, as a single-line string. Using an
# env var (instead of a checked-in file) is what makes this safe to deploy
# on ephemeral platforms like Railway, where you generally don't want
# secrets sitting in the filesystem/repo.
FIREBASE_CREDENTIALS_JSON = os.environ.get("FIREBASE_CREDENTIALS_JSON", "")

# --- AI provider selection ---
# Episode generation/validation ("main") and DM classification/setting-choice
# ("fast") can each independently use a different provider -- e.g. Claude
# for the writing, a cheaper Gemini/Grok model for the classification calls.
# Supported: "anthropic", "gemini", "openai", "grok". See services/ai_providers/.
AI_PROVIDER_MAIN = os.environ.get("AI_PROVIDER_MAIN", "anthropic")
AI_PROVIDER_FAST = os.environ.get("AI_PROVIDER_FAST", "anthropic")

# Optional explicit model overrides. Leave blank to use the selected
# provider's own sensible built-in default for that role (see each file in
# services/ai_providers/ for exactly what that default is).
AI_MODEL_MAIN = os.environ.get("AI_MODEL_MAIN", "")
AI_MODEL_FAST = os.environ.get("AI_MODEL_FAST", "")

# --- Per-provider API keys (only the ones for your selected provider(s) are required) ---
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")     # Gemini
XAI_API_KEY = os.environ.get("XAI_API_KEY", "")           # Grok
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# --- Narrative pacing bounds (per spec: interval 1h-1d, duration up to 29d) ---
MIN_INTERVAL_HOURS = 1
MAX_INTERVAL_HOURS = 24
MIN_DURATION_DAYS = 1
MAX_DURATION_DAYS = 29

# --- Tunable story constants ---
DEFAULT_SCENE_LENGTH_EPISODES = 6        # episodes before a scene/location change
MAX_FEATURED_CHARACTERS_PER_EPISODE = 5  # soft cap suggested to the AI
CAST_CANDIDATE_POOL_CAP = 15             # max candidate profiles shown to the AI per episode
LOCATION_AUTOCOMPLETE_LIMIT = 25         # Discord's own hard cap on autocomplete suggestions shown at once

# --- Just-in-time generation window (spec: begin generating 1-5 min before post time) ---
JIT_GENERATION_WINDOW_MINUTES = 5
SCHEDULER_TICK_SECONDS = 60
STUCK_GENERATION_TIMEOUT_MINUTES = 15    # auto-recover a lock left over from a crash mid-generation
MAX_GENERATION_BACKOFF_MINUTES = 60      # cap on how long a repeatedly-failing guild gets skipped between retries

# --- Local backup (opt-in: leave LOCAL_BACKUP_DIR unset to disable entirely) ---
# A ONE-DIRECTIONAL periodic export of story/character/episode data to a
# local path -- meant for a Railway Volume (see README) so it survives
# container restarts. This is NOT a live second data store the bot reads
# from; see the README's "Local backup" section for why a true dual-write
# design was deliberately avoided.
LOCAL_BACKUP_DIR = os.environ.get("LOCAL_BACKUP_DIR", "")
LOCAL_BACKUP_INTERVAL_MINUTES = int(os.environ.get("LOCAL_BACKUP_INTERVAL_MINUTES", "30"))

# If True, a DM rejected by content validation OR blocked by a unique-role
# conflict (see fb.claim_unique_character) does NOT consume the user's
# one-submission-per-interval slot, so they can immediately try again.
# Spec text reads literally as "only the first DM is processed" regardless
# of outcome, so this defaults to False; flip it if you'd rather let people
# retry right away after a rejection.
ALLOW_RETRY_AFTER_REJECTED_DM = False

# --- Narrative arc stage thresholds (fraction of total episodes elapsed) ---
ARC_INTRODUCTION_END = 0.15
ARC_RISING_ACTION_END = 0.70
ARC_CLIMAX_END = 0.90
# anything beyond ARC_CLIMAX_END, up to and including the final episode, is "resolution"


def validate_config():
    """Raise a clear error at startup if required secrets are missing,
    instead of failing confusingly later on first use. Only requires the
    API key(s) for whichever provider(s) are actually selected."""
    from services.ai_providers import PROVIDER_API_KEY_ENV, SUPPORTED_PROVIDERS

    missing = []
    if not DISCORD_BOT_TOKEN:
        missing.append("DISCORD_BOT_TOKEN")
    if not FIREBASE_CREDENTIALS_JSON:
        missing.append("FIREBASE_CREDENTIALS_JSON")

    for provider in {AI_PROVIDER_MAIN.lower(), AI_PROVIDER_FAST.lower()}:
        env_name = PROVIDER_API_KEY_ENV.get(provider)
        if env_name is None:
            raise RuntimeError(
                f"Unknown AI provider {provider!r} in AI_PROVIDER_MAIN/AI_PROVIDER_FAST. "
                f"Supported: {', '.join(SUPPORTED_PROVIDERS)}"
            )
        if not globals()[env_name]:
            missing.append(env_name)

    if missing:
        raise RuntimeError(
            "Missing required environment variables: " + ", ".join(missing)
            + ". Copy .env.example to .env and fill these in (see README.md)."
        )
