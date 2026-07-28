"""
Shared slash-command checks. Kept in its own module so cogs don't need to
import from one another.
"""
import discord
from discord import app_commands

import config
from services import story_logic


async def _is_owner_or_admin(interaction: discord.Interaction) -> bool:
    """
    The actual permission logic, exposed separately from the
    app_commands.check() wrapper below so it's directly unit-testable with
    a plain stand-in object instead of a real discord.Interaction (see
    tests/test_checks.py).

    True for the server's real Discord owner, OR for anyone listed in
    BOT_ADMIN_USER_IDS -- which lets the bot's operator run owner-only
    commands on any server the bot is in, without needing to actually own
    each one.
    """
    if interaction.guild is None:
        return False
    if interaction.user.id == interaction.guild.owner_id:
        return True
    admin_ids = story_logic.parse_admin_ids(config.BOT_ADMIN_USER_IDS_RAW)
    return interaction.user.id in admin_ids


def is_guild_owner():
    """Restricts a command to the server owner or a configured bot admin --
    see _is_owner_or_admin above."""
    return app_commands.check(_is_owner_or_admin)
