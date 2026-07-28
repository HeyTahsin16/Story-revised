"""
Entry point. Loads configuration, initializes Firebase, sets up the Discord
client with the required intents, loads all cogs, registers a global slash
command error handler, and runs the bot.
"""
import asyncio

import discord
from discord import app_commands
from discord.ext import commands

import config
from services import firebase_service as fb

INTENTS = discord.Intents.default()
INTENTS.message_content = True   # required to read DM text content
INTENTS.dm_messages = True       # required to receive DMs at all
INTENTS.members = True           # optional but recommended -- see README ("Discord setup")

EXTENSIONS = (
    "cogs.setup_cog",
    "cogs.owner_cog",
    "cogs.dm_cog",
    "cogs.scheduler_cog",
    "cogs.backup_cog",
)


class StoryBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=INTENTS)

    async def setup_hook(self):
        for extension in EXTENSIONS:
            await self.load_extension(extension)
        await self.tree.sync()

    async def on_ready(self):
        print(f"Logged in as {self.user} (id={self.user.id})")


def build_bot() -> StoryBot:
    bot = StoryBot()

    @bot.tree.error
    async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            message = "Only the server owner can use this command."
        else:
            print(f"[app_command_error] {error!r}")
            message = "Something went wrong running that command."

        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    return bot


async def main():
    config.validate_config()
    fb.init_firebase()
    bot = build_bot()
    async with bot:
        await bot.start(config.DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
