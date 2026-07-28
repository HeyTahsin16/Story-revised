"""
Owner-only controls:
  /story-dashboard  -- view episode/scene stats
  /story-killswitch -- instantly terminate the story
  /story-twist      -- queue a plot twist for the next episode
  /story-image      -- post a custom image + caption directly, bypassing the AI entirely
"""
import datetime as dt

import discord
from discord import app_commands
from discord.ext import commands

from services import firebase_service as fb
from services import story_logic as logic
from cogs.checks import is_guild_owner


class OwnerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="story-dashboard", description="View current story stats (owner only).")
    @is_guild_owner()
    async def story_dashboard(self, interaction: discord.Interaction):
        story = await fb.get_story(interaction.guild.id)
        if not story:
            await interaction.response.send_message("No story has been set up yet.", ephemeral=True)
            return

        total = story.get("total_episodes", 0)
        current = story.get("current_episode", 0)
        remaining_overall = max(0, total - current)

        scene_started = story.get("scene_started_at_episode", 1)
        scene_length = story.get("scene_length", 0)
        next_number = story.get("next_episode_number", current + 1)
        episodes_into_scene = max(0, next_number - scene_started)
        remaining_in_scene = max(0, scene_length - episodes_into_scene)

        embed = discord.Embed(title="Story Dashboard", color=discord.Color.dark_teal())
        embed.add_field(name="Status", value=story.get("status", "unknown"), inline=True)
        embed.add_field(name="Episodes remaining overall", value=str(remaining_overall), inline=True)
        embed.add_field(name="Episodes left in current scene", value=str(remaining_in_scene), inline=True)
        embed.add_field(name="Current episode", value=f"{current} / {total}", inline=True)
        embed.add_field(name="Current location", value=str(story.get("current_location_key") or "TBD"), inline=True)
        embed.add_field(
            name="Pending for next episode",
            value=(
                f"{len(story.get('pending_suggestions', {}) or {})} suggestion(s), "
                f"{len(story.get('pending_twists', []) or [])} twist(s)"
            ),
            inline=True,
        )

        next_time = story.get("next_episode_time")
        if next_time and story.get("status") == "active":
            now = dt.datetime.now(dt.timezone.utc)
            embed.add_field(
                name="Next episode in",
                value=logic.compute_time_remaining_string(next_time, now),
                inline=True,
            )

        failures = story.get("consecutive_generation_failures", 0)
        if failures:
            retry_after = story.get("next_retry_after")
            now = dt.datetime.now(dt.timezone.utc)
            retry_note = (
                f"retrying in {logic.compute_time_remaining_string(retry_after, now)}"
                if retry_after else "retrying soon"
            )
            embed.add_field(
                name="Generation is failing",
                value=(
                    f"{failures} attempt(s) in a row failed ({retry_note}). "
                    "Check your hosting logs for the actual error -- a common cause is an "
                    "AI provider quota/rate limit being exceeded."
                ),
                inline=False,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="story-killswitch", description="Instantly stop the current story (owner only).")
    @is_guild_owner()
    async def story_killswitch(self, interaction: discord.Interaction):
        story = await fb.get_story(interaction.guild.id)
        if not story or story.get("status") not in ("active", "pending"):
            await interaction.response.send_message("There's no active story to stop.", ephemeral=True)
            return

        await fb.update_story(interaction.guild.id, {"status": "killed"})
        await interaction.response.send_message(
            "Story stopped. No further episodes will be generated.", ephemeral=True
        )

    @app_commands.command(name="story-twist", description="Submit a plot twist to influence the next episode (owner only).")
    @app_commands.describe(twist="The twist to weave into the next episode")
    @is_guild_owner()
    async def story_twist(self, interaction: discord.Interaction, twist: str):
        story = await fb.get_story(interaction.guild.id)
        if not story or story.get("status") != "active":
            await interaction.response.send_message("There's no active story right now.", ephemeral=True)
            return

        await fb.add_twist(interaction.guild.id, twist)
        await interaction.response.send_message(
            "Noted -- that twist will be worked into the next episode.", ephemeral=True
        )

    @app_commands.command(name="story-image", description="Post a custom image with caption directly, bypassing the AI (owner only).")
    @app_commands.describe(image="Image to post", caption="Text to post alongside the image")
    @is_guild_owner()
    async def story_image(self, interaction: discord.Interaction, image: discord.Attachment, caption: str):
        story = await fb.get_story(interaction.guild.id)
        if not story:
            await interaction.response.send_message("No story has been set up yet.", ephemeral=True)
            return

        channel = self.bot.get_channel(int(story["channel_id"]))
        if channel is None:
            channel = await self.bot.fetch_channel(int(story["channel_id"]))

        await interaction.response.defer(ephemeral=True)
        file = await image.to_file()
        await channel.send(content=caption, file=file)
        await interaction.followup.send("Posted.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(OwnerCog(bot))
