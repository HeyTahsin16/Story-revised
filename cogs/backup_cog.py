"""
Periodic local backup of story data (opt-in, see config.LOCAL_BACKUP_DIR)
plus a manual /story-backup command for an on-demand snapshot. See
services/backup_service.py's module docstring and the README's "Local
backup" section for why this is a one-directional export to a Railway
Volume, not a live second data store -- Firebase/Firestore remains the
only store the bot actually reads from and writes to during normal
operation.
"""
import discord
from discord import app_commands
from discord.ext import commands, tasks

import config
from services import backup_service
from cogs.checks import is_guild_owner


class BackupCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        if config.LOCAL_BACKUP_DIR:
            self.periodic_backup.start()

    def cog_unload(self):
        if self.periodic_backup.is_running():
            self.periodic_backup.cancel()

    @tasks.loop(minutes=config.LOCAL_BACKUP_INTERVAL_MINUTES)
    async def periodic_backup(self):
        result = await backup_service.run_backup()
        if result.get("success"):
            print(f"[backup_cog] periodic backup OK: {result['guild_count']} guild(s) -> {result['path']}")
        elif result.get("enabled"):
            print(f"[backup_cog] periodic backup FAILED: {result.get('error')}")

    @periodic_backup.before_loop
    async def before_periodic_backup(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="story-backup", description="Write an immediate local backup snapshot (owner only).")
    @is_guild_owner()
    async def story_backup(self, interaction: discord.Interaction):
        if not config.LOCAL_BACKUP_DIR:
            await interaction.response.send_message(
                "Local backups aren't configured -- set LOCAL_BACKUP_DIR to a path on a "
                "mounted Railway Volume to enable this (optional; Firebase is always the "
                "main database). See the README's \"Local backup\" section.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        result = await backup_service.run_backup()
        if result.get("success"):
            await interaction.followup.send(
                f"Backed up {result['guild_count']} active stor{'y' if result['guild_count'] == 1 else 'ies'} "
                f"to `{result['path']}`.",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(f"Backup failed: {result.get('error')}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(BackupCog(bot))
