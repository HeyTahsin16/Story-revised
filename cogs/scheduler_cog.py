"""
Background loop that checks Firestore every tick for stories whose next
episode is due (within the just-in-time generation window) and, if so,
generates and posts it.

This is the ONLY place that decides "is it time yet" -- all state lives in
Firestore, so a container restart on an ephemeral host just resumes
correctly on the next tick instead of losing track of anything.
"""
import datetime as dt

import discord
from discord.ext import commands, tasks

import config
from services import firebase_service as fb
from services import story_logic as logic
from services import episode_engine as engine
from data.locations import BACKGROUNDS_DIR

EMBED_DESCRIPTION_LIMIT = 4000  # headroom under Discord's 4096 embed description cap


class SchedulerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.tick.start()

    def cog_unload(self):
        self.tick.cancel()

    @tasks.loop(seconds=config.SCHEDULER_TICK_SECONDS)
    async def tick(self):
        now = dt.datetime.now(dt.timezone.utc)
        try:
            stories = await fb.list_active_stories()
        except Exception as exc:
            print(f"[scheduler] failed to list active stories: {exc}")
            return

        for story in stories:
            guild_id = int(story["guild_id"])
            try:
                await self._maybe_run_story(guild_id, story, now)
            except Exception as exc:
                print(f"[scheduler] error processing guild {guild_id}: {exc}")
                # Back off exponentially before retrying THIS guild again,
                # instead of hammering it every single tick -- a persistent
                # failure (an exhausted daily AI quota, a bad key, a
                # sustained outage) will just keep failing identically, and
                # retrying every 60 seconds anyway is exactly what burned
                # through a 20-requests/day free-tier quota in minutes.
                failures = story.get("consecutive_generation_failures", 0) + 1
                backoff_minutes = logic.compute_generation_backoff_minutes(
                    failures, max_minutes=config.MAX_GENERATION_BACKOFF_MINUTES
                )
                try:
                    await fb.update_story(
                        guild_id,
                        {
                            "generation_in_progress": False,
                            "consecutive_generation_failures": failures,
                            "next_retry_after": now + dt.timedelta(minutes=backoff_minutes),
                        },
                    )
                    print(f"[scheduler] guild {guild_id}: backing off {backoff_minutes} minute(s) (failure #{failures})")
                except Exception:
                    pass

    @tick.before_loop
    async def before_tick(self):
        await self.bot.wait_until_ready()

    async def _maybe_run_story(self, guild_id: int, story: dict, now: dt.datetime):
        next_retry_after = story.get("next_retry_after")
        if next_retry_after is not None:
            if next_retry_after.tzinfo is None:
                next_retry_after = next_retry_after.replace(tzinfo=dt.timezone.utc)
            if now < next_retry_after:
                return

        next_time = story.get("next_episode_time")
        if next_time is None:
            return
        if next_time.tzinfo is None:
            next_time = next_time.replace(tzinfo=dt.timezone.utc)

        if story.get("generation_in_progress"):
            started = story.get("generation_started_at")
            if started and started.tzinfo is None:
                started = started.replace(tzinfo=dt.timezone.utc)
            if started and (now - started).total_seconds() > config.STUCK_GENERATION_TIMEOUT_MINUTES * 60:
                # A previous attempt almost certainly crashed mid-generation
                # (e.g. a container restart) -- recover instead of hanging forever.
                await fb.update_story(guild_id, {"generation_in_progress": False})
            else:
                return

        if not logic.is_within_jit_window(next_time, now, config.JIT_GENERATION_WINDOW_MINUTES):
            return

        await fb.update_story(guild_id, {"generation_in_progress": True, "generation_started_at": now})

        channel = self.bot.get_channel(int(story["channel_id"]))
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(int(story["channel_id"]))
            except discord.HTTPException:
                await fb.update_story(guild_id, {"generation_in_progress": False})
                return

        if story["next_episode_number"] == 1:
            result = await engine.run_episode_1(guild_id, story)
        else:
            result = await engine.run_next_episode(guild_id, story)

        await self._post_episode(channel, result)

        updates = {
            "generation_in_progress": False,
            "current_episode": result["episode_number"],
            "next_episode_number": result["episode_number"] + 1,
            "next_episode_time": next_time + dt.timedelta(hours=story["interval_hours"]),
            "story_summary": result.get("story_summary", story.get("story_summary", "")),
            "consecutive_generation_failures": 0,
            "next_retry_after": None,
        }
        if result["episode_number"] == 1:
            updates["current_location_key"] = result["location"]["key"]
            updates["scene_started_at_episode"] = 1
        else:
            if result.get("next_location_key"):
                updates["current_location_key"] = result["next_location_key"]
            if result.get("next_scene_started_at"):
                updates["scene_started_at_episode"] = result["next_scene_started_at"]
            if result.get("is_story_finale"):
                updates["status"] = "completed"

        await fb.update_story(guild_id, updates)

        if result["episode_number"] == 1:
            await self._post_call_to_action(channel)

    async def _post_episode(self, channel: discord.abc.Messageable, result: dict):
        chunks = logic.split_into_chunks(result["text"], EMBED_DESCRIPTION_LIMIT)
        if not chunks:
            chunks = ["(the author generated an empty episode -- check your AI provider's logs)"]
        multi_part = len(chunks) > 1

        image_path = BACKGROUNDS_DIR / f"{result['location']['key']}.png"
        file = discord.File(image_path, filename=image_path.name) if image_path.exists() else None

        for i, chunk in enumerate(chunks):
            title = f"Episode {result['episode_number']}"
            if multi_part:
                title += f" (part {i + 1}/{len(chunks)})"
            embed = discord.Embed(title=title, description=chunk, color=discord.Color.dark_teal())

            if i == 0:
                embed.set_footer(text=result["location"]["display_name"])
                if file:
                    embed.set_image(url=f"attachment://{file.filename}")
                    await channel.send(embed=embed, file=file)
                    continue
            await channel.send(embed=embed)

    async def _post_call_to_action(self, channel: discord.abc.Messageable):
        await channel.send("DM me with your stories.")


async def setup(bot: commands.Bot):
    await bot.add_cog(SchedulerCog(bot))
