"""
Handles all direct messages sent to the bot: guild disambiguation (a user
might share more than one active-story server with the bot), rate limiting
(one processed DM per interval window), AI content validation, and
character storage.

Logs at every meaningful step (not just failures) with a consistent
[dm_cog guild=... user=...] prefix, specifically so the whole pipeline is
traceable from hosting logs alone -- this came out of a real incident
where a bug several steps into processing raised an exception nothing was
catching, so the user got no reply at all and there was nothing in the
logs pointing at why. _process_for_guild's body now also has a top-level
safety-net try/except: whatever happens, the user gets SOME reply and the
logs get SOME context, even for a failure mode nobody anticipated.
"""
import datetime as dt

import discord
from discord.ext import commands

import config
from services import firebase_service as fb
from services import ai_service as ai
from services import story_logic as logic


def _log(guild_id, user_id, message: str):
    print(f"[dm_cog guild={guild_id} user={user_id}] {message}")


class DMCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if message.guild is not None:
            return  # this cog only handles DMs

        print(f"[dm_cog] DM received from user={message.author.id} ({len(message.content)} chars)")

        pending = await fb.get_pending_disambiguation(message.author.id)
        if pending:
            await self._handle_disambiguation_reply(message, pending)
            return

        await self._handle_submission(message, message.content)

    async def _candidate_guilds(self, user: discord.abc.User) -> list:
        """Guilds this user shares with the bot AND that have an active
        story. Tries the member cache first (fast, no API call), and falls
        back to an explicit fetch (reliable even without the Members
        intent, at the cost of one API call per guild when the cache
        misses -- acceptable since this only runs on an incoming DM)."""
        candidates = []
        for guild in self.bot.guilds:
            member = guild.get_member(user.id)
            if member is None:
                try:
                    member = await guild.fetch_member(user.id)
                except (discord.NotFound, discord.HTTPException):
                    continue
            story = await fb.get_story(guild.id)
            if story and story.get("status") == "active":
                candidates.append({"id": guild.id, "name": guild.name})
        return candidates

    async def _handle_submission(self, message: discord.Message, text: str):
        candidates = await self._candidate_guilds(message.author)
        _log("?", message.author.id, f"resolved {len(candidates)} candidate guild(s): {[c['name'] for c in candidates]}")

        if not candidates:
            await message.channel.send(
                "I don't see an active story we're both part of right now. "
                "Ask the server owner to run the setup command first."
            )
            return

        if len(candidates) > 1:
            listing = "\n".join(f"{i + 1}. {c['name']}" for i, c in enumerate(candidates))
            await fb.set_pending_disambiguation(
                message.author.id,
                [str(c["id"]) for c in candidates],
                text,
            )
            await message.channel.send(
                "You're part of more than one active story. Which server is this for?\n"
                f"{listing}\n"
                "Reply with the number."
            )
            return

        await self._process_for_guild(message, candidates[0]["id"], text)

    async def _handle_disambiguation_reply(self, message: discord.Message, pending: dict):
        choice = message.content.strip()
        candidate_ids = pending.get("candidate_guild_ids", [])
        if not choice.isdigit() or not (1 <= int(choice) <= len(candidate_ids)):
            await message.channel.send(f"Please reply with a number from 1 to {len(candidate_ids)}.")
            return

        guild_id = int(candidate_ids[int(choice) - 1])
        _log(guild_id, message.author.id, "disambiguation resolved, processing original submission")
        await fb.clear_pending_disambiguation(message.author.id)
        await self._process_for_guild(message, guild_id, pending.get("pending_text", ""))

    async def _process_for_guild(self, message: discord.Message, guild_id: int, text: str):
        user_id = message.author.id
        try:
            await self._process_for_guild_inner(message, guild_id, text)
        except Exception as exc:
            # Safety net: whatever this is, it wasn't one of the specific
            # failure modes already handled below with their own message.
            # Without this, an unanticipated bug here (this exact class of
            # bug has happened before -- see firebase_service.py's history)
            # means the user gets silent non-response and the logs show
            # nothing beyond discord.py's own generic event-error handler.
            _log(guild_id, user_id, f"UNHANDLED exception in submission processing: {exc!r}")
            await message.channel.send(
                "Something went wrong on my end processing that -- please try again in a few minutes."
            )

    async def _process_for_guild_inner(self, message: discord.Message, guild_id: int, text: str):
        user_id = message.author.id

        story = await fb.get_story(guild_id)
        if not story or story.get("status") != "active":
            _log(guild_id, user_id, f"story not active (status={story.get('status') if story else None}), rejecting")
            await message.channel.send("That story isn't currently active.")
            return

        next_number = story["next_episode_number"]
        allowed = await fb.claim_submission_window(guild_id, user_id, next_number)
        _log(guild_id, user_id, f"rate-limit claim for episode window {next_number}: {'allowed' if allowed else 'already used'}")

        if not allowed:
            now = dt.datetime.now(dt.timezone.utc)
            remaining = logic.compute_time_remaining_string(story["next_episode_time"], now)
            await message.channel.send(f"Come back in {remaining}.")
            return

        roster = await self._living_roster_excluding(guild_id, user_id)
        _log(guild_id, user_id, f"living roster for conflict-check has {len(roster)} other character(s)")

        try:
            classification = await ai.classify_submission(text, existing_roster=roster)
        except Exception as exc:
            _log(guild_id, user_id, f"classify_submission raised: {exc!r}")
            await message.channel.send("Something went wrong processing that -- please try again in a few minutes.")
            return

        _log(
            guild_id, user_id,
            f"classification: is_valid={classification.get('is_valid')} "
            f"has_character_update={classification.get('has_character_update')} "
            f"has_suggestion={classification.get('has_suggestion')}",
        )

        if not classification.get("is_valid"):
            if config.ALLOW_RETRY_AFTER_REJECTED_DM:
                await fb.reset_submission_window(guild_id, user_id)
            reason = classification.get("rejection_reason") or "Could you tell me a bit more about your character?"
            _log(guild_id, user_id, f"rejected: {reason[:200]!r}")
            await message.channel.send(reason)
            return

        confirmations = []

        if classification.get("has_character_update"):
            update_fields = {
                "display_name": classification["character_label"],
                "mention_style": classification["mention_style"],
                "backstory": classification["backstory_summary"],
                "ping_opt_out": classification["wants_ping_opt_out"],
                "last_submission_for_episode": next_number,
            }
            try:
                # A second, code-guaranteed check (not just the AI's
                # judgment call above): atomically verifies no OTHER
                # currently-alive character already holds the same
                # normalized label before writing, closing the race where
                # two DMs claiming "the king" arrive close enough together
                # that both could otherwise pass the check above.
                collision = await fb.claim_unique_character(guild_id, user_id, update_fields)
            except Exception as exc:
                _log(guild_id, user_id, f"claim_unique_character raised: {exc!r}")
                await message.channel.send(
                    "Something went wrong saving your character -- please try again in a few minutes."
                )
                return

            if collision:
                _log(guild_id, user_id, f"character claim blocked: collides with {collision!r}")
                if config.ALLOW_RETRY_AFTER_REJECTED_DM:
                    await fb.reset_submission_window(guild_id, user_id)
                await message.channel.send(
                    f'Someone already has a claim on "{collision}" in this story. '
                    "Want to try a different angle -- a rival claimant, someone who serves "
                    "them, or a distinct character entirely?"
                )
                return

            _log(guild_id, user_id, f"character claimed: {classification['character_label']!r}")
            confirmations.append("your character is in the mix for the next episode")

        if classification.get("has_suggestion"):
            suggestion = logic.truncate_suggestion(classification.get("suggested_development", ""))
            if suggestion:
                try:
                    await fb.add_suggestion(guild_id, user_id, suggestion)
                    if not classification.get("has_character_update"):
                        # Keep an existing character (if any) marked as
                        # freshly active this window so it's still
                        # prioritized for featuring -- but never create a
                        # character record just because someone sent a
                        # suggestion with no character info.
                        await fb.touch_character_submission(guild_id, user_id, next_number)
                except Exception as exc:
                    _log(guild_id, user_id, f"storing suggestion raised: {exc!r}")
                    await message.channel.send(
                        "Something went wrong saving that suggestion -- please try again in a few minutes."
                    )
                    return
                _log(guild_id, user_id, f"suggestion stored: {suggestion[:200]!r}")
                confirmations.append(
                    "your suggestion will be considered for the next episode -- no promises, "
                    "the story might still go a different way"
                )

        if not confirmations:
            # Shouldn't normally happen given the is_valid check above, but
            # stay graceful if the model returned an inconsistent result.
            _log(guild_id, user_id, "classification was valid but yielded no usable content -- inconsistent model output")
            await message.channel.send(
                "Got it, but I couldn't find a character update or a usable suggestion in "
                "that -- feel free to try again."
            )
            return

        await message.channel.send("Got it -- " + " and ".join(confirmations) + ".")

    @staticmethod
    async def _living_roster_excluding(guild_id: int, user_id: int) -> list:
        """Other currently-alive/revived characters in this story, for the
        AI's semantic unique-role-conflict check. Deliberately not capped:
        missing a character here would mean missing a real conflict, so
        completeness matters more than prompt size for this particular list
        (realistic story rosters are small enough that this is a non-issue)."""
        characters = await fb.list_characters(guild_id)
        user_id_str = str(user_id)
        return [
            {"label": c.get("display_name", ""), "backstory": c.get("backstory", "")}
            for c in characters
            if c.get("user_id") != user_id_str and c.get("status") != "deceased"
        ]


async def setup(bot: commands.Bot):
    await bot.add_cog(DMCog(bot))
