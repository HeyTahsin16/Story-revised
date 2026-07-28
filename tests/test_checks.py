"""
Unit tests for cogs/checks.py's permission predicate. Uses a plain
SimpleNamespace stand-in instead of a real discord.Interaction -- the
predicate only ever touches .guild, .guild.owner_id, and .user.id, so a
duck-typed stub is enough and avoids needing a live Discord connection.
"""
import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# config.py reads env vars at import time; these need to exist before any
# import of config happens anywhere in the test session.
os.environ.setdefault("DISCORD_BOT_TOKEN", "x")
os.environ.setdefault("FIREBASE_CREDENTIALS_JSON", "{}")
os.environ.setdefault("ANTHROPIC_API_KEY", "x")

import pytest

import config
from cogs.checks import _is_owner_or_admin


def _fake_interaction(user_id: int, guild_owner_id: int = None, has_guild: bool = True):
    guild = SimpleNamespace(owner_id=guild_owner_id) if has_guild else None
    return SimpleNamespace(guild=guild, user=SimpleNamespace(id=user_id))


@pytest.mark.asyncio
async def test_real_server_owner_is_allowed(monkeypatch):
    monkeypatch.setattr(config, "BOT_ADMIN_USER_IDS_RAW", "")
    interaction = _fake_interaction(user_id=100, guild_owner_id=100)
    assert await _is_owner_or_admin(interaction) is True


@pytest.mark.asyncio
async def test_random_member_is_denied(monkeypatch):
    monkeypatch.setattr(config, "BOT_ADMIN_USER_IDS_RAW", "")
    interaction = _fake_interaction(user_id=999, guild_owner_id=100)
    assert await _is_owner_or_admin(interaction) is False


@pytest.mark.asyncio
async def test_configured_bot_admin_is_allowed_on_a_server_they_dont_own(monkeypatch):
    monkeypatch.setattr(config, "BOT_ADMIN_USER_IDS_RAW", "555555555555555555")
    interaction = _fake_interaction(user_id=555555555555555555, guild_owner_id=100)
    assert await _is_owner_or_admin(interaction) is True


@pytest.mark.asyncio
async def test_bot_admin_works_across_multiple_different_servers(monkeypatch):
    monkeypatch.setattr(config, "BOT_ADMIN_USER_IDS_RAW", "555555555555555555")
    server_a = _fake_interaction(user_id=555555555555555555, guild_owner_id=100)
    server_b = _fake_interaction(user_id=555555555555555555, guild_owner_id=200)
    assert await _is_owner_or_admin(server_a) is True
    assert await _is_owner_or_admin(server_b) is True


@pytest.mark.asyncio
async def test_non_admin_non_owner_still_denied_even_with_admins_configured(monkeypatch):
    monkeypatch.setattr(config, "BOT_ADMIN_USER_IDS_RAW", "555555555555555555")
    interaction = _fake_interaction(user_id=999, guild_owner_id=100)
    assert await _is_owner_or_admin(interaction) is False


@pytest.mark.asyncio
async def test_dm_context_with_no_guild_is_denied(monkeypatch):
    monkeypatch.setattr(config, "BOT_ADMIN_USER_IDS_RAW", "999")
    interaction = _fake_interaction(user_id=999, has_guild=False)
    assert await _is_owner_or_admin(interaction) is False
