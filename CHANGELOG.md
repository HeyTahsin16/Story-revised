# Changelog

## 1.6.0

Found the actual reason DMs still didn't work after 1.5.0 -- a real code
bug this time, not a quota issue -- plus the requested comprehensive DM
logging.

### Fixed: every character claim was broken
`services/firebase_service.py`'s `claim_unique_character` (the transaction
that checks for duplicate role claims and saves a character) was calling
`transaction.get(chars_ref)` where `chars_ref` is a `CollectionReference`.
Confirmed directly via the installed library that `CollectionReference` is
NOT a subclass of `Query` (`issubclass(CollectionReference, Query)` is
`False`), despite superficially supporting query-like methods -- and
`Transaction.get()` only accepts a `DocumentReference` or a `Query`, so
this raised `ValueError('Value for argument "ref_or_query" must be a
DocumentReference or a Query.')` on literally every attempt. This is why
DMs stopped working even after the Gemini quota issue was addressed: any
character update reached this line and failed, every single time, not
intermittently.

Fixed by calling `chars_ref.stream(transaction=transaction)` instead --
confirmed via the library's own signature that `CollectionReference.stream()`
accepts a `transaction` parameter directly, which is the correct way to do
a transactional read of a whole collection. Audited every other Firestore
call in the file by hand afterward; this was the only instance of the
mistake.

### Added: comprehensive DM pipeline logging (as requested)
`cogs/dm_cog.py` was rewritten to log every meaningful step, not just
failures, with a consistent `[dm_cog guild=... user=...]` prefix: DM
received, candidate guild resolution, rate-limit claim result,
classification summary (valid/character-update/suggestion flags),
character claim result (success/collision/error), suggestion storage
result. The entire per-DM processing flow is now wrapped in a top-level
safety-net try/except, so ANY failure -- including a class of bug nobody
anticipated, exactly like the one above -- always produces both a specific
log line and a user-facing reply. Previously, an exception raised deep in
the flow (like the one this release fixes) had no catch block around it at
all: the user got total silence, and hosting logs showed nothing beyond
discord.py's own generic internal event-error handler.

## 1.5.0

Root cause found for "it doesn't even start the first episode" -- the
1.4.0 debug logging did exactly its job and surfaced it in the very next
log dump: `429 RESOURCE_EXHAUSTED... limit: 20, model: gemini-3.6-flash`.
Two separate things needed fixing.

### The actual constraint: Gemini free tier is 20 requests/day
This isn't fixable by better retry logic -- see the README's expanded
Gemini section for the full math, but in short: a 24-episode story needs
48+ AI calls minimum (2 per episode: generate + validate), which already
exceeds a 20/day cap more than double before counting anything else. This
needs a decision on the Google Cloud/AI Studio side (enable billing) or a
provider/story-size change, not a code fix.

### Fixed: the bot's own retry logic was making the quota problem worse
Confirmed directly from the log: a single failed episode-generation
attempt could burn up to 6 actual API calls (3 outer retries, each trying
both a thinking-disabled AND a thinking-default request), and the
scheduler retried a failing guild every 60 seconds with zero backoff. On a
20/day quota, that combination exhausts it within minutes of story setup,
before Episode 1 ever has a chance to succeed once.

- `GeminiProvider` now recognizes `RESOURCE_EXHAUSTED` specifically and
  stops immediately -- no fallback attempt, no outer retries -- since a
  quota error will not resolve within the few seconds a backoff would wait,
  and retrying just spends more of an already-exhausted quota. Cuts a
  failed attempt from up to 6 API calls down to 1-2.
- Whether `thinking_budget=0` is supported is now learned ONCE per process
  and cached, instead of re-discovered (at the cost of an extra failed
  call) on every single generation. Verified with mocked tests that a
  second call on the same provider instance only makes 1 API call instead
  of 2 once this is known.
- New: `cogs/scheduler_cog.py` now backs off exponentially (2, 4, 8...
  minutes, capped at `MAX_GENERATION_BACKOFF_MINUTES`, default 60) for a
  guild whose generation keeps failing, tracked via
  `consecutive_generation_failures` / `next_retry_after` on the story
  document, instead of retrying every single 60-second tick regardless of
  how many times it just failed. Resets to zero on the next success.
- `/story-dashboard` now shows a "Generation is failing" field with the
  failure count and next retry time when this is happening, instead of
  that only being visible in hosting logs.

### Other
- Fixed a real duplication bug introduced while adding the dashboard
  field above (caught immediately via re-reading the diff, not shipped).
- 3 new tests for the backoff calculation; the quota-awareness logic in
  `GeminiProvider` and the scheduler's skip/reset behavior were both
  verified with dedicated mocked-response tests covering: an immediate
  quota error, a rejection-then-quota-error sequence, the caching behavior
  across two calls, and confirming genuine transient errors still retry
  normally (91 tests total).

## 1.4.0

Follow-up to 1.3.0 after the DM issue was confirmed to persist on a live
Gemini deployment, plus a new opt-in local backup feature.

### Fixed: a real bug in the 1.3.0 Gemini fix itself
- The previous fix (disable Gemini's "thinking" tokens to maximize the
  visible-output budget) had a bug: if `thinking_budget=0` isn't supported
  by a given model (plausible for a lighter/faster tier) and raised an
  error, the retry loop just retried the SAME unsupported request three
  times instead of ever falling back -- confirmed by testing both failure
  shapes (rejection vs. empty response) against mocked responses. Restructured
  so the fallback (retry once without the thinking override) happens
  within the SAME attempt, immediately, not after burning through the
  outer retry loop.
- Also discovered (by reading the google-genai SDK source directly) that
  Gemini's `.text` property explicitly excludes "thought" parts from its
  result -- meaning if reasoning consumes most (not all) of the token
  budget, the visible answer can get cut off mid-sentence rather than
  coming back empty. This matches the original "hangs lopsided from"
  screenshot closely enough to be a strong candidate for the root cause,
  though it's not been confirmed against a live key.

### Added: logging on every AI-response parse/call failure
- Every JSON parse failure (`ai_service.py`'s three JSON-producing calls)
  and every raised exception from the classification call itself
  (`dm_cog.py`) now prints the raw model output or error to stdout, which
  Railway captures in its log stream. Previously, a parse failure only
  produced a generic user-facing message with no way to see what the model
  actually returned -- this was the main blocker to diagnosing the DM issue
  further from the outside.
- `extract_json` also now strips trailing commas (`{"a": 1,}`) before
  giving up, at every extraction layer -- a common small LLM JSON mistake
  that's otherwise a total parse failure despite the content being
  unambiguous. 3 new tests.

### Added: local backup (optional, Firebase remains the only live database)
- Explicitly did NOT implement "write everything to both Firestore and
  Railway storage live" as literally requested -- see the README's new
  "Local backup" section for the full reasoning, but in short: keeping two
  live stores in sync is a hard problem in its own right, and a naive dual
  write is a more likely source of new bugs (silent data drift between the
  two) than a meaningful reliability win for this use case.
- What's there instead:
  1. `services/firebase_service.py` Firestore calls now retry with backoff
     on transient errors (`_run_with_retry`) -- covers the actually likely
     failure mode (a brief network blip) with no added risk.
  2. `services/backup_service.py`: an opt-in (`LOCAL_BACKUP_DIR`),
     one-directional periodic export of every active story's full
     config/roster/episode log to local disk -- meant to sit on a Railway
     Volume so it survives restarts. The bot never reads from this file;
     it's a fallback export for manual recovery, not a second live store.
  3. New owner command `/story-backup` for an on-demand snapshot.
- README documents how to actually attach a Railway Volume for this to
  persist anywhere durable, plus how to pull a backup file off it if you
  ever need to.
- 6 new tests, including real (not mocked) temporary-directory file I/O
  for the write/rotate logic.

### Other
- 9 new tests overall (88 total).

## 1.3.0

Bug-fix release driven by real deployment feedback (Railway logs + live
Discord screenshots) -- all four items below trace to reports from an
actual running bot, not just code review.

### Fixed: DM submissions failing with "something went wrong reading that submission"
- Root cause confirmed by testing the old code against real-shaped model
  output: `_extract_json` only handled a response that was bare JSON or a
  fence with literally nothing else around it. A one-sentence preamble
  before the fence, a remark after it, or even just an uppercase `JSON`
  tag on the fence all broke it -- any of which is a common way for a
  model to format output despite being told not to, especially a
  faster/smaller model on the classification path.
- Rewrote as `story_logic.extract_json` (moved out of `ai_service.py` so
  it's pure and unit-testable) with three fallback layers: parse the whole
  trimmed string, search for a fenced block anywhere in the text, then
  fall back to the substring between the first `{` and the last `}`. 11
  new tests cover every shape above plus genuinely unparseable input.
- All three JSON-producing prompts (classifier, validator, setting-choice)
  were also made more emphatic: "the first character of your response must
  be `{` and the last must be `}`" -- a second, complementary layer of
  defense on top of the more forgiving parser.

### Fixed: starting location never announced to players
- The onboarding message posts at `/story-setup` time, but if the owner
  left the location blank, the AI didn't actually pick one until Episode 1
  generated -- which could be hours later depending on the interval. There
  was no way for players to know what to write characters for in that gap
  (a wizard concept doesn't fit a story that turns out to be set in a
  hospital).
- The location (owner-picked or AI-picked) is now resolved during
  `/story-setup` itself and stated explicitly in the onboarding message:
  `**Setting:** Foggy Cemetery -- leaning headstones, distant crow calls`.
  `episode_engine.run_episode_1` no longer picks a location at all; it just
  uses what setup already resolved (with a defensive random fallback only
  for stale/malformed data, which should never trigger in practice).
- Since resolving an AI-picked location is a real network call,
  `/story-setup` now defers its interaction response first (Discord's
  non-deferred response window is 3 seconds) and falls back to a random
  pool location if that AI call fails, so a provider hiccup can never break
  story setup entirely.

### Fixed: episodes reading as too short
- Target length roughly doubled: Episode 1 from 3-5 paragraphs to 7-10,
  regular episodes from 3-6 to 6-9, with matching token budget increases
  (900/1200 -> 2000).
- Hardened the Gemini provider specifically: "thinking" Gemini models can
  spend part of the output token budget on hidden reasoning before writing
  any visible text, which can produce short or empty-looking output once
  that budget runs out -- there's no separate budget for it unless you ask.
  `GeminiProvider` now explicitly disables thinking by default and falls
  back to the model's default thinking behavior only if that yields empty
  text. (Not confirmed as the actual cause without knowing which provider
  was in use -- but a real, specific failure mode worth closing regardless.)
- Longer episodes made truncation more likely to actually trigger, so
  silent mid-sentence truncation was replaced with proper multi-message
  splitting at paragraph boundaries (`story_logic.split_into_chunks`, 6 new
  tests) -- a long episode now posts as "Episode 4 (part 1/2)" etc. rather
  than losing its ending.

### New: key names highlighted in bold
- The author now bolds significant names the first time they appear each
  episode -- an invented in-story setting name (the model names its own
  specific version of a location, e.g. "Saint Jude's Infirmary" for the
  "Abandoned Hospital" pool entry, which isn't something code can predict
  and pre-format), other named locations, notable entities, and each
  featured player character's name/title. Verified bold markers and mention
  tokens don't interfere with each other in `apply_mentions`.

### Other
- Fixed a Firestore deprecation warning visible in the reported Railway
  logs (positional `.where()` arguments -> `filter=FieldFilter(...)`).
- 17 new tests (79 total).

## 1.2.0

### Players can suggest story developments, not just character flavor
- New: a DM can now propose an actual development -- a character's next
  move, an interaction with someone else's character, a world event -- in
  addition to (or instead of) character info. The author treats it as
  creative input to weigh on merit, never a command to execute:
  `EPISODE_SYSTEM_PROMPT` in `services/ai_service.py` explicitly states the
  author retains full discretion, that most episodes should adopt zero or
  one suggestion (not rewrite around every one, every episode), and that a
  suggestion affecting *another* player's character needs a real narrative
  reason to land, not just because one player asked.
- The DM classifier now screens for a third category alongside low-effort
  content and unique-role conflicts: story-hijacking attempts (claiming
  absolute/god-like authority, scripting an entire episode or the ending
  verbatim). This is evaluated separately from whether the character-update
  half of a DM is valid, so a fine character submission attached to an
  overreaching "suggestion" still gets the character part accepted.
- A code-level cap (`story_logic.truncate_suggestion`, default 400 chars)
  backs up the AI's judgment call so a single suggestion can't function as
  an attempt to ghostwrite the whole episode regardless of what the model
  decides.
- Suggestions are stored on the story document (`pending_suggestions`, a
  user_id -> text map), not on character documents -- a suggestion with no
  character info attached would otherwise create a malformed "ghost"
  character record. This also meant moving DM rate-limit tracking off the
  character document entirely (now its own `submission_windows`
  subcollection) so the same problem couldn't occur there either.
- Cast-candidate selection for each episode now guarantees every fresh
  submission (a character update and/or a suggestion) a slot ahead of
  filler candidates, instead of an even shuffle across both groups --
  otherwise a fresh suggestion could occasionally get crowded out of the
  prompt entirely on an active server. See `story_logic.prioritize_cast_candidates`.
- The continuity validator now also reports `adopted_suggestion_user_ids`,
  logged on each episode for transparency; `/story-dashboard` shows the
  count of suggestions and twists pending for the next episode.

### Writing quality, without scraping real stories for "inspiration"
- Deliberately did NOT build a feature to fetch real copyrighted text
  (Reddit posts, books, movies, anime, light/visual novels) into the
  generation prompt as reference material -- feeding a model someone else's
  work and asking it to draw on it risks the output echoing that work too
  closely, which is a real exposure for whoever runs the bot, not just an
  abstract concern.
- Instead, `EPISODE_SYSTEM_PROMPT` now explicitly instructs for
  craft-level qualities: concrete sensory grounding, character interiority,
  showing rather than stating emotion, varied sentence rhythm, and avoiding
  cliche/over-explaining. See the README's "Player influence vs. authorial
  control" section for the fuller reasoning.

### Bot-admin override
- New `BOT_ADMIN_USER_IDS` env var (comma-separated Discord user ids).
  Anyone listed gets owner-level access to all `/story-*` commands on any
  server the bot is in, alongside that server's real owner -- useful for
  managing or testing across servers you don't personally own.
  `cogs/checks.py`'s permission logic was refactored into a standalone
  `_is_owner_or_admin` coroutine specifically so it's unit-testable with a
  plain stand-in object instead of a live Discord connection.

### Other
- 19 new tests (62 total): suggestion truncation, admin-id parsing,
  cast-candidate prioritization (including "fresh submissions always beat
  the cap"), and the full owner/bot-admin permission matrix.

## 1.1.0

### Multi-provider AI support
- Added Google Gemini, xAI Grok, and OpenAI as alternatives to Anthropic.
  Select independently per role via `AI_PROVIDER_MAIN` (episode writing +
  continuity validation) and `AI_PROVIDER_FAST` (DM classification +
  opening-location choice) -- e.g. Claude for the writing, Grok for the
  cheaper classification calls, or any other mix.
- New package: `services/ai_providers/`, behind a single `AIProvider`
  interface. Adding a fifth provider later means one new file plus one
  branch in `ai_providers/__init__.py`'s factory -- nothing in
  `ai_service.py` (the actual prompts) needs to change.
- Each provider ships a sensible built-in default model per role; override
  with `AI_MODEL_MAIN` / `AI_MODEL_FAST` if you want something else.
- `config.validate_config()` now only requires the API key(s) for whichever
  provider(s) you actually selected, not all four.

### Starting location: searchable, not hard-coded to 25
- `/story-setup` previously only accepted a free-text theme. It now has a
  `starting_location` option backed by Discord autocomplete, searching the
  full 100+ location pool by name, key, or category as you type.
- Discord cap on a static `choices=[]` list is 25 entries -- nowhere near
  the size of the location pool. Autocomplete is the actual mechanism past
  that: instead of pre-registering a fixed list, the bot re-searches the
  whole pool on every keystroke and returns up to 25 matching suggestions
  (that per-response count is a separate, unavoidable Discord UI cap, but
  the searchable pool behind it isn't capped at all -- see
  `data/locations.search_locations`).

### Atmosphere / vibe notes for the opening episode
- New optional `atmosphere` option on `/story-setup`. Accepts either a
  short comma-separated list of mood words ("dark, eerie, foggy, midnight")
  or a full descriptive sentence -- both are treated as inspiration, not
  as text to reproduce. The episode-1 prompt explicitly instructs the
  model to weave the elements in and never copy the wording verbatim.

### Unique-role conflicts (the "two people both claim to be the king" problem)
- New two-layer defense, closing the gap in first-come-first-served that
  only checking against "the previous claimant" would leave open for a
  third or fourth person:
  1. **Deterministic (code, always on):** `find_label_collision` in
     `services/story_logic.py` normalizes case/articles/whitespace and
     rejects an exact/near-exact duplicate claim outright -- no AI
     judgment involved, fully unit tested, and correct for any number of
     simultaneous claimants because every new submission is checked
     against the full current roster, not just the last person.
  2. **Semantic (AI-assisted):** `classify_submission` is now also given
     the story's other living characters and screens for a paraphrased
     claim to the same singular role (e.g. "I rule this kingdom" vs "I am
     the king"), while explicitly told not to flag roles many people can
     hold (soldier, villager, merchant, ...).
- A character who dies is excluded from both checks, so a now-vacant
  singular role (a dead king's throne) is correctly open to the next
  claimant -- no special-case code needed, it falls out of "only check
  against the currently-alive roster."
- Closed a genuine race condition, not just a hypothetical one: discord.py
  schedules every incoming DM as its own independent `asyncio.Task`, so two
  DMs claiming the same role milliseconds apart are not automatically
  serialized. The claim is now a single Firestore transaction
  (`claim_unique_character`) that reads the whole roster and writes the new
  character atomically, instead of a separate check-then-write.
- A rejected submission (either reason) still respects
  `ALLOW_RETRY_AFTER_REJECTED_DM` the same way content-validation
  rejections always have.

### Other
- `requirements.txt` now includes `google-genai` and `openai` alongside
  `anthropic` by default so any provider choice works without extra
  installs; each provider still gives a clear "pip install X" error if you
  trim requirements.txt down and pick one anyway.
- 19 new unit tests (43 total) covering the label-collision logic
  (including the 3+-claimant and death/succession scenarios explicitly) and
  the location search function.

## 1.0.0

Initial release: interval-based collaborative storytelling bot with
owner-configured pacing, AI-selected/owner-preset opening location, DM-based
character submission with anti-griefing screening and rate limiting,
ping-consent-aware `@mention` formatting, automatic scene changes, a
continuity-validation second AI call, and owner controls (dashboard, kill
switch, plot twists, manual image injection). See the project README for
full feature details.
