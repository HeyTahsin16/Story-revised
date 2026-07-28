"""
Server-owner setup/configuration command: /story-setup

Configures a new story, computes the episode count, schedules Episode 1,
and posts the required onboarding instructions in the target channel.

The starting location is chosen via autocomplete search over the full
100+ location pool rather than a hard-coded choices=[] list, which Discord
caps at 25 entries -- see data/locations.search_locations for how the
search itself works, and cogs/checks.py / README.md for more on why.

Whether the owner picked a location or left it blank, the location is
resolved to a concrete choice HERE, at setup time -- not deferred until
Episode 1 actually generates, hours later. Without that, players have no
idea what setting to write characters for during the whole gap between
setup and Episode 1 posting (a wizard concept submitted for what turns out
to be a modern hospital doesn't fit), so the onboarding message below
always names the actual location.
"""
import datetime as dt
import random

import discord
from discord import app_commands
from discord.ext import commands

import config
from services import firebase_service as fb
from services import ai_service as ai
from services import story_logic as logic
from data.locations import LOCATIONS, LOCATIONS_BY_KEY, search_locations
from cogs.checks import is_guild_owner


async def _location_autocomplete(interaction: discord.Interaction, current: str):
    matches = search_locations(current, limit=config.LOCATION_AUTOCOMPLETE_LIMIT)
    return [app_commands.Choice(name=loc["display_name"], value=loc["key"]) for loc in matches]


class SetupCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="story-setup", description="Configure and start a new collaborative story.")
    @app_commands.describe(
        channel="Channel where episodes will be posted",
        interval_hours="Hours between episodes (1-24)",
        duration_days="Total story length in days (1-29)",
        starting_location="Search and pick a starting location (leave blank to let the AI pick)",
        atmosphere="Optional mood/vibe/theme for the opening -- keywords (dark, eerie, foggy) or a sentence both work",
    )
    @app_commands.autocomplete(starting_location=_location_autocomplete)
    @is_guild_owner()
    async def story_setup(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        interval_hours: app_commands.Range[int, config.MIN_INTERVAL_HOURS, config.MAX_INTERVAL_HOURS],
        duration_days: app_commands.Range[int, config.MIN_DURATION_DAYS, config.MAX_DURATION_DAYS],
        starting_location: str = "",
        atmosphere: str = "",
    ):
        existing = await fb.get_story(interaction.guild.id)
        if existing and existing.get("status") == "active":
            await interaction.response.send_message(
                "There's already an active story in this server. Use /story-killswitch first if you want to start over.",
                ephemeral=True,
            )
            return

        starting_location = starting_location.strip()
        if starting_location and starting_location not in LOCATIONS_BY_KEY:
            await interaction.response.send_message(
                "That doesn't match one of the available locations -- start typing in the "
                "starting_location field and pick one of the suggestions Discord shows you "
                "(or leave it blank to let the AI pick).",
                ephemeral=True,
            )
            return

        # Resolving an AI-picked location is a real network call and can
        # take a few seconds -- defer now so Discord doesn't time out the
        # interaction waiting on it (a bare response has a 3-second budget).
        await interaction.response.defer(ephemeral=True)

        if starting_location:
            location = LOCATIONS_BY_KEY[starting_location]
        else:
            try:
                choice = await ai.choose_opening_location(LOCATIONS)
                location = LOCATIONS_BY_KEY.get(choice.get("location_key")) or random.choice(LOCATIONS)
            except Exception:
                # Never let an AI hiccup block story setup -- fall back to
                # a plain random pick from the same pool.
                location = random.choice(LOCATIONS)

        total_episodes = logic.compute_total_episodes(interval_hours, duration_days)
        now = dt.datetime.now(dt.timezone.utc)
        next_time = now + dt.timedelta(hours=interval_hours)

        await fb.create_story(
            interaction.guild.id,
            {
                "channel_id": str(channel.id),
                "owner_id": str(interaction.user.id),
                "interval_hours": interval_hours,
                "duration_days": duration_days,
                "total_episodes": total_episodes,
                "current_episode": 0,
                "next_episode_number": 1,
                "status": "active",
                "starting_location_key": location["key"],
                "atmosphere_notes": atmosphere,
                "current_location_key": None,
                "scene_started_at_episode": 1,
                "scene_length": config.DEFAULT_SCENE_LENGTH_EPISODES,
                "story_summary": "",
                "next_episode_time": next_time,
                "generation_in_progress": False,
                "pending_twists": [],
                "pending_suggestions": {},
                "consecutive_generation_failures": 0,
                "next_retry_after": None,
            },
        )

        await interaction.followup.send(
            f"Story configured. Episode 1 posts in {channel.mention} in about {interval_hours} hour(s), "
            f"opening in {location['display_name']}, with {total_episodes} total episodes over "
            f"{duration_days} day(s).",
            ephemeral=True,
        )

        await channel.send(self._onboarding_text(interval_hours, total_episodes, duration_days, location))

    @staticmethod
    def _onboarding_text(interval_hours: int, total_episodes: int, duration_days: int, location: dict) -> str:
        return (
            "**A new collaborative story is starting in this channel.**\n\n"
            f"**Setting:** {location['display_name']} -- {location['mood']}\n\n"
            "Here's how it works:\n"
            f"- A new episode posts roughly every {interval_hours} hour(s), for {total_episodes} episodes "
            f"over about {duration_days} day(s) total.\n"
            "- To join in, send the bot a direct message describing your character: who they are and a short "
            "backstory. Keep the setting above in mind so your idea actually fits the world.\n"
            "- You can also suggest what happens next -- your character's next move, an interaction with "
            "someone else's character, an event in the world. The author (AI) weighs it like any writer "
            "would: it might get used as-is, adapted loosely, or set aside if it doesn't serve the story -- "
            "most episodes use zero or one suggestion, not everyone's at once.\n"
            "- The story's overall direction and ending are the author's call, not any single player's -- "
            "submissions that try to dictate the whole plot or claim total authority over it get turned away.\n"
            "- Only your first DM within each interval window is processed. If you DM again before the next "
            "episode posts, you'll get a note asking you to come back later -- that's expected, not an error.\n"
            "- If you don't want to be @ mentioned when your character appears, just say so in your DM.\n"
            "- Any other characters you mention in your own backstory become minor background characters -- "
            "only your own character is tied to your account.\n"
            "- If you claim a role that only one person can hold (like being *the* king), and someone already "
            "has it, we'll ask you to pick a different angle -- first come, first served, and it opens back up "
            "if that character ever dies.\n\n"
            "DM me with your stories."
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(SetupCog(bot))
