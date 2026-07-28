# Collaborative Storytelling Discord Bot

**Version 1.6.0** -- see `CHANGELOG.md` for release history.

An interval-based Discord bot that writes an ongoing, serialized story in a
channel, incorporating characters and backstories DMed in by server members
while keeping full control of the plot. Built in Python on discord.py,
Firebase Firestore for state, and your choice of Claude, Gemini, Grok, or
OpenAI for generation.

## Features

- Owner configures a channel, posting interval (1-24 hours), and story
  duration (1-29 days); the bot computes the total episode count and paces
  a real narrative arc (introduction -> rising action -> climax ->
  resolution) to land the ending on the final episode.
- Episode 1 is pure world-building (no dialogue, no characters). The owner
  picks a starting location by searching the full 100+ location pool via
  autocomplete (or leaves it blank for the AI to pick), and can optionally
  describe an atmosphere/vibe/theme -- as keywords or a full sentence -- that
  gets woven into the opening prose without ever being copied verbatim.
  Either way, the location is resolved and announced in the onboarding
  message immediately at setup, not left a mystery until Episode 1 actually
  posts, so players know what to write characters for from the start.
- The author bolds significant names the first time they appear each
  episode -- an invented in-story setting name, other named locations, and
  each featured character's name/title -- and episodes that run long post
  as clearly-labeled multiple parts rather than getting cut off.
- Members submit characters by DMing the bot; submissions are screened for
  low-effort/immersion-breaking content AND for unique-role conflicts (two
  people both trying to be "the king"), rate-limited to one processed DM
  per interval window, and rendered with correct `@mention` formatting
  (or none at all, if the member opted out of pings) -- enforced in code,
  not left to the AI's memory.
- Players can also suggest what happens next -- their character's next move,
  an interaction with someone else's character, a world event -- as
  creative input the author weighs on merit, not a command it executes.
  The author can adopt it, adapt it loosely, or set it aside; most episodes
  use zero or one suggestion, not everyone's at once. Submissions that try
  to dictate the whole plot or claim total authority over the story are
  screened out before they ever reach the author.
- A character's status (alive / deceased / revived) is tracked privately
  and persistently; the AI is fed this state on every generation and
  double-checked by a second "continuity editor" model call afterward, so
  a dead character can't accidentally reappear across a 100+ episode run.
  A dead character's role also reopens automatically for a new claimant.
- Scene/location changes happen automatically every few episodes, with the
  AI given advance notice so it can wrap up the current location naturally.
- Owner-only controls: live dashboard, instant kill switch, plot twist
  injection, and a manual "post this image with this caption" command that
  bypasses the AI entirely (for light-novel-style illustration drops). A
  configurable `BOT_ADMIN_USER_IDS` also grants owner-level access on any
  server the bot is in, not just servers you personally own.
- Bring your own AI: Claude, Gemini, Grok, and OpenAI are all supported out
  of the box, independently configurable for episode writing vs. the
  cheaper classification calls.
- Designed for ephemeral hosts like Railway: all state lives in Firestore,
  not local disk, and generation only ever starts 1-5 minutes before the
  scheduled post time (never early), with automatic recovery if a
  container restarts mid-generation.

## Player influence vs. authorial control

As of 1.2, players aren't limited to submitting flavor text -- they can
suggest actual developments, and the author (whichever AI model you've
configured) treats those as real creative input, not just decoration. That
said, a submission can never fully hand over the story:

- **First come, first served on singular roles**, checked against every
  currently-alive character, not just the last claimant -- see the
  duplicate-role notes below.
- **A suggestion never overrides authorial discretion.** The generation
  prompt explicitly tells the model it's never obligated to use a
  suggestion, and that most episodes should use zero or one, lightly
  reinterpreted -- not rewrite the story's direction around every
  suggestion, every episode.
- **A suggestion targeting another player's character** (not the
  suggester's own) needs a real narrative reason to land, not just because
  one player asked -- no one can unilaterally decide someone else's
  character's fate through a "suggestion."
- **Content screening runs before generation, not after.** The DM
  classifier explicitly rejects attempts to claim absolute authority over
  the story ("I am god", scripting the entire plot/ending verbatim) as a
  distinct category from ordinary low-effort spam.

On taking inspiration from real literature (Reddit stories, books, movies,
anime, published fiction): this bot does not fetch or feed in real
copyrighted text as source material, and I'd recommend against adding that
yourself. If the model ever echoed a real work too closely because it was
handed that work as "inspiration," that's a real legal exposure for
whoever operates the bot, not just an abstract concern. What actually moved
here instead is craft-level prompting: `EPISODE_SYSTEM_PROMPT` in
`services/ai_service.py` now explicitly pushes for concrete sensory detail,
character interiority, earned emotional beats, and varied prose rhythm --
the things that make writing feel human, achieved by asking the model to
write better, not by copying anyone's specific work. It won't resolve every
version of "should AI write fiction at all," but the player-suggestion
system above is, in a real sense, a direct answer to it: more of the
story's actual content now comes from real people's ideas, not just
character flavor text, with the author's job being to weave that into
something coherent rather than generate a human-free story from nothing.

## Project structure

```
bot.py                  Entry point
config.py                Env vars + tunable constants
CHANGELOG.md              Release history
cogs/
  setup_cog.py            /story-setup (incl. location autocomplete)
  owner_cog.py             /story-dashboard, /story-killswitch, /story-twist, /story-image
  dm_cog.py                 DM ingestion: disambiguation, rate limiting, validation, role-conflict checks
  scheduler_cog.py           Background loop: JIT episode generation + posting
  backup_cog.py               Periodic local backup loop + /story-backup (optional, see README)
  checks.py                  Shared owner-only permission check
services/
  firebase_service.py       Async Firestore wrapper (all persistent state)
  ai_service.py               Provider-agnostic prompt logic (generation + validation + classification)
  ai_providers/                 One AIProvider implementation per vendor
    base.py                       Abstract interface
    anthropic_provider.py
    gemini_provider.py
    openai_compatible_provider.py   Shared by OpenAI and Grok (Grok's API is OpenAI-compatible)
  episode_engine.py            Orchestrates one episode end-to-end
  backup_service.py              Optional local backup export (see README)
  story_logic.py                Pure narrative math + role-collision logic -- no I/O, unit tested
data/
  locations.py             The 100+ location pool, plus its autocomplete search function
backgrounds/               Location artwork (see backgrounds/README.md)
scripts/
  generate_placeholder_backgrounds.py   Regenerate placeholder art if you add locations
tests/
  test_story_logic.py      Unit tests: narrative math, mentions, role-collision, suggestions
  test_location_search.py    Unit tests: the autocomplete search function
  test_checks.py               Unit tests: owner/bot-admin permission logic
  test_backup_service.py        Unit tests: backup serialization + file rotation (real temp-dir I/O)
```

## Requirements

- Python 3.11+
- A Discord bot application
- An API key for at least one supported AI provider (Anthropic, Gemini, Grok, or OpenAI)
- A Firebase project with Firestore (Native mode)

## 1. Discord setup

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and create a New Application, then add a Bot to it.
2. Under **Bot**, enable these Privileged Gateway Intents:
   - **Message Content Intent** (required -- the bot reads DM text)
   - **Server Members Intent** (recommended -- speeds up figuring out which
     server a DM is for; the bot still works without it via a fallback API
     call, just with slightly more latency/API usage on servers where a
     user hasn't been recently active)
3. Copy the bot token into `DISCORD_BOT_TOKEN`.
4. Optional: to set `BOT_ADMIN_USER_IDS`, enable Discord's User Settings ->
   Advanced -> Developer Mode, then right-click your own username anywhere
   and choose "Copy User ID".
5. Under **OAuth2 -> URL Generator**, select scopes `bot` and
   `applications.commands`, and permissions: Send Messages, Embed Links,
   Attach Files, Read Message History, Use Slash Commands. Use the
   generated URL to invite the bot to your server.

## 2. Firebase setup

1. Create a project at the [Firebase Console](https://console.firebase.google.com/) and enable **Firestore Database** in Native mode.
2. Go to **Project Settings -> Service Accounts -> Generate new private key**. This downloads a JSON file.
3. Paste the *entire contents* of that JSON file as a single-line string into `FIREBASE_CREDENTIALS_JSON`. This env-var approach (rather than committing the file) is what makes the bot safe to deploy on a host like Railway.

No manual Firestore index setup is needed -- every query this bot makes is a single-field filter or single-field sort.

## 3. AI provider setup

Pick a provider for `AI_PROVIDER_MAIN` (episode writing + continuity
validation) and `AI_PROVIDER_FAST` (DM classification + opening-location
choice) -- they can be the same provider or different ones. Supported
values and where to get each key:

| Provider | `AI_PROVIDER_*` value | API key env var | Get a key at |
|---|---|---|---|
| Anthropic (Claude) | `anthropic` | `ANTHROPIC_API_KEY` | console.anthropic.com |
| Google Gemini | `gemini` | `GOOGLE_API_KEY` | aistudio.google.com/apikey |
| xAI Grok | `grok` | `XAI_API_KEY` | console.x.ai |
| OpenAI | `openai` | `OPENAI_API_KEY` | platform.openai.com/api-keys |

You only need to set the API key(s) for the provider(s) you actually pick;
`config.validate_config()` checks only those. Both settings default to
`anthropic` if left unset. Each provider has a sensible built-in default
model per role (see `services/ai_providers/`); override with
`AI_MODEL_MAIN` / `AI_MODEL_FAST` if you want a specific model instead.

Mixing providers is fine and can save cost -- e.g. Claude or GPT for the
actual writing, a cheaper/faster model for the classification calls that
run on every DM.

## 4. Run locally

```bash
cp .env.example .env
# fill in .env: Discord token, Firebase credentials JSON, and your chosen
# AI provider(s) + matching API key(s) from the table above
pip install -r requirements.txt
python bot.py
```

## 5. Deploy on Railway

1. Push this project to a GitHub repo.
2. In Railway, **New Project -> Deploy from GitHub repo**, select it.
3. In the service's **Variables** tab, add `DISCORD_BOT_TOKEN`,
   `FIREBASE_CREDENTIALS_JSON`, and whichever `AI_PROVIDER_MAIN` /
   `AI_PROVIDER_FAST` + matching API key variable(s) you're using (see the
   AI provider table above).
4. Railway will detect `railway.json` (start command `python bot.py`) and
   deploy automatically on every push. No exposed port is needed -- this is
   a background worker, not a web service.

Because all state lives in Firestore, redeploys and restarts are safe: the
scheduler just resumes on its next tick.

## Local backup (optional)

Firebase/Firestore is always the live database -- the bot only ever reads
from and writes to Firestore during normal operation. This section is
about an *optional* fallback export on top of that, for extra peace of
mind if Firestore ever has an extended outage.

**Why not just write everything to two databases at once?** That was the
literal first version of this idea, and it's worth explaining why it
didn't make the cut: keeping two live data stores in sync is a genuinely
hard distributed-systems problem, not a small addition. If a write to one
store succeeds and the other fails (a real possibility, not an edge case),
the two silently drift apart, and now the bot's behavior depends on which
store happens to answer a given read -- a much worse failure mode than
"Firestore was briefly slow," and the kind of bug that's miserable to
track down after the fact. A oneway periodic export sidesteps that
entirely: the bot's own behavior never depends on this file existing,
being current, or even being writable.

**What's actually implemented instead:**
1. Firestore calls now retry with backoff on transient errors (network
   blips, brief unavailability) -- `services/firebase_service.py`'s
   `_run_with_retry`. This covers the far more likely failure mode (a
   momentary hiccup) with no added complexity or risk.
2. A periodic, one-directional JSON export of every active story
   (config + full character roster + full episode log) to a local
   directory -- `services/backup_service.py`. Enabled only if you set
   `LOCAL_BACKUP_DIR`; left unset (the default), none of this runs at all.
3. A manual `/story-backup` (owner only) for an on-demand snapshot, e.g.
   right before you do something you're nervous about.

**To make the backup actually survive a restart**, point `LOCAL_BACKUP_DIR`
at a Railway Volume rather than the plain container filesystem (which
resets on every deploy, same as anywhere else in this repo):

1. In the Railway project canvas, right-click (or use the Command Palette)
   and create a new Volume.
2. Set its mount path to something like `/data` (any path works, just make
   `LOCAL_BACKUP_DIR` match it exactly).
3. Set `LOCAL_BACKUP_DIR=/data` (or whatever you picked) in your service's
   Variables tab.
4. Optionally set `LOCAL_BACKUP_INTERVAL_MINUTES` (default 30).

Volumes are billed separately by Railway (per GB/minute) and are one per
service. If you ever need to actually recover from a backup file, use
`railway volume files download` (Railway CLI) to pull `story_backup.json`
off the volume -- there's no automatic re-import into Firestore built here,
since restoring is inherently a "look at what you have and decide" manual
step, not something to automate blindly.

## Commands

| Command | Who | What |
|---|---|---|
| `/story-setup` | owner | Configure channel, interval, duration; search-select a starting location (or leave blank for AI-picked) and optionally describe the atmosphere/vibe; starts the story |
| `/story-dashboard` | owner | Episodes remaining overall, episodes left in the current scene |
| `/story-killswitch` | owner | Instantly stop the story |
| `/story-twist` | owner | Queue a plot twist for the next episode |
| `/story-image` | owner | Post a custom image + caption directly (no AI involved) |
| `/story-backup` | owner | Write an immediate local backup snapshot (only useful if `LOCAL_BACKUP_DIR` is set) |
| DM the bot | anyone | Submit/update your character's identity and backstory |

"Owner" means the actual Discord server owner, not just anyone with
Administrator permission, matching the spec this bot was built from.

## Customizing locations / artwork

See `backgrounds/README.md` for the full list of expected file names. Drop
your own art in with matching file names to replace the placeholders --
no code changes required.

## Tunable constants

Most behavior that isn't spelled out as a strict rule lives in `config.py`:
scene length before a location change, how many candidate characters get
shown to the AI per episode, the JIT generation window, and whether a
rejected DM consumes that user's one-submission-per-interval slot
(`ALLOW_RETRY_AFTER_REJECTED_DM`, off by default -- see the comment there
for the reasoning).

## Design notes / known limitations

- **DM processing is fully logged and never fails silently.** Every step
  (`cogs/dm_cog.py`) logs its outcome with a `[dm_cog guild=... user=...]`
  prefix -- rate-limit result, classification summary, character claim
  result, suggestion storage -- so a DM's whole path through the pipeline
  is traceable from hosting logs alone. `_process_for_guild` also has a
  top-level safety-net try/except around the entire flow: whatever fails,
  the user gets a reply and the log gets a stack-trace-free but specific
  line, instead of silence (which is exactly what used to happen -- an
  exception several steps in with nothing catching it specifically).
- **JSON parsing from AI responses** uses `story_logic.extract_json`, which
  tries a bare parse, then a fenced block found anywhere in the text, then
  a first-`{`-to-last-`}` substring, with trailing-comma cleanup at each
  layer -- specifically because models (even when explicitly told not to)
  sometimes wrap JSON in a code fence, add a sentence before or after it,
  leave a trailing comma, or some combination of all three. If a DM ever
  fails with a generic "something went wrong" message, every parse failure
  now logs the raw model output (truncated) to stdout, which Railway (or
  wherever you're hosting) captures in its log stream -- check there first;
  `ai_service.py`'s three JSON-producing calls and `dm_cog.py`'s outer
  exception handler around the AI call itself all log on failure.
- **Gemini free-tier quota is almost certainly too small for this bot.**
  Confirmed from real deployment logs, not speculation: Gemini's free tier
  caps `gemini-3.6-flash` (the default main-role model) at **20 requests
  per day**. Each episode needs at least 2 calls (generate + validate); a
  story with 24 episodes -- e.g. a 3-hour interval over 3 days -- needs 48+
  calls just for that, before counting DM classification or any retries.
  No amount of retry-logic improvement changes this math: if your story's
  episode count exceeds roughly 10 (half the daily quota, leaving room for
  validation calls), the bot WILL run out of quota before finishing,
  regardless of how efficiently it uses each request. To actually run a
  full story on Gemini, either enable billing on the Google AI Studio/Cloud
  project backing your API key (paid tier quotas are far higher), reduce
  the story's total episode count substantially, or use a different
  provider for `AI_PROVIDER_MAIN`.
- **What IS fixed, independent of the quota size:** the bot used to make
  the problem worse than it needed to be. `GeminiProvider` was retrying a
  quota-exhausted request with a different parameter combination (up to 6
  API calls for a single failed generation attempt) instead of recognizing
  a `RESOURCE_EXHAUSTED` error can't be fixed by retrying at all, and the
  scheduler was retrying a failing guild every 60 seconds with no backoff,
  which is what actually burned through a 20/day quota within minutes in
  the log that surfaced this. Both are fixed: a quota error now stops
  immediately (1-2 calls instead of 6), and a guild whose generation keeps
  failing backs off exponentially (2, 4, 8... minutes, capped at
  `MAX_GENERATION_BACKOFF_MINUTES`) instead of being retried every tick.
  `/story-dashboard` also now shows when a story is stuck failing, instead
  of that only being visible in hosting logs.
- **Gemini "thinking" models** more generally: they draw hidden reasoning
  tokens from the SAME `max_output_tokens` budget as visible text (the
  SDK's `.text` property explicitly excludes "thought" parts, so if
  reasoning consumes most of that budget, the model can get cut off
  partway through the actual answer -- a short, mid-sentence-looking
  response is the visible symptom). `GeminiProvider` disables thinking by
  default and falls back to the model's own default thinking behavior,
  learned once per process rather than re-discovered on every call (see
  above -- this also matters for quota efficiency, not just correctness).
- **DM-to-server matching**: if a member shares more than one
  *active-story* server with the bot, their first DM triggers a
  disambiguation prompt ("which server is this for?") rather than guessing.
- **Suggestions share the same rate limit as character updates**: one DM
  processed per interval window covers both, and a single DM can contain
  either, both, or neither. Rate-limit tracking lives in its own
  `submission_windows` subcollection rather than on the character
  document, specifically so a pure suggestion (no character info at all)
  never creates a malformed "ghost" character record.
- **Bot-admin override**: `BOT_ADMIN_USER_IDS` (comma-separated Discord
  user ids) grants owner-level `/story-*` access on any server the bot is
  in, alongside that server's actual owner -- see `cogs/checks.py`.
- **Continuity**: every episode is checked by a second model call before
  being finalized, which can catch and correct Episode 1 accidentally
  including dialogue (one automatic regeneration attempt). Deeper plot
  contradictions are flagged in `contradiction_notes` in the validator's
  output but don't currently block posting -- if you want stricter
  enforcement, that's the place in `services/ai_service.py` to extend.
- **Rate limiting** is enforced with a Firestore transaction, so two DMs
  arriving at nearly the same moment can't both slip through.
- **Mention formatting** (`Doctor @user` vs `Beelzebub (@user)`, or no
  mention at all for opted-out users) is applied deterministically in code
  after generation, not left to the model to remember -- see
  `apply_mentions` in `services/story_logic.py`.
- **Starting location search**: Discord hard-caps a static `choices=[]`
  option list at 25 entries. `/story-setup`'s `starting_location` option
  uses autocomplete instead -- `data/locations.search_locations` re-searches
  the full 100+ pool on every keystroke and returns up to 25 matches, so
  the searchable pool isn't capped even though the suggestion dropdown is
  (that part's a Discord UI limit, not something any bot can bypass).
- **Unique-role conflicts** ("I'm the king" / "I'm the king too" / a third
  and fourth person trying the same thing): handled in two layers. First,
  a deterministic, code-guaranteed check (`find_label_collision` in
  `story_logic.py`) normalizes case/articles/whitespace and blocks an
  exact/near-exact duplicate outright -- first claimant wins, and it's
  checked against the *entire* current roster each time, so it's correct
  for any number of later claimants, not just a second one. Second, the AI
  classification call is separately given the story's living cast and
  tries to catch paraphrased duplicates the literal check would miss. A
  character's role reopens automatically once they're marked deceased --
  no special succession code needed, it falls out of only checking
  against currently-*alive* characters. The claim-and-write happens in a
  single Firestore transaction (not a separate check-then-write) because
  discord.py runs each incoming DM as its own concurrent task, so two
  same-instant claims are a real race, not just a theoretical one.

## Tests

The modules with zero external dependencies (no Discord/Firebase/AI-provider
calls) are `services/story_logic.py` and `data/locations.py`, covering
episode-count math, arc pacing, mention substitution, the JIT scheduling
window, the location autocomplete search, the unique-role-collision logic
(including the "3+ people claim the same role" and "role reopens after
death" scenarios explicitly), suggestion truncation, cast-candidate
prioritization, admin-id parsing, robust JSON extraction from raw AI
responses, and paragraph-aware message splitting for long episodes.
`services/backup_service.py`'s serialization and file-rotation logic is
covered with real temporary-directory I/O (not mocked -- this is plain
local disk access, not a network call). `cogs/checks.py`'s owner/bot-admin
permission logic is also covered, using a plain stand-in object instead of
a real `discord.Interaction` (88 tests total):

```bash
pip install -r requirements-dev.txt
pytest tests/
```

The AI-provider integrations and live Firestore transactions aren't covered
by these tests (they need real credentials this repo obviously can't ship)
-- test those against your own keys/project before relying on them in
production.

## License

MIT -- see `LICENSE`.
