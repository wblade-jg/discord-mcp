"""Tests smoke del ``Bot``.

Feature: bot-cache-behavior, Smoke: inyección del cliente y sin ``requests``
"""

import ast
from pathlib import Path

from discord_mcp.bot import Bot
from discord_mcp.discord_api import DiscordApiClient
from discord_mcp.models.discord_bot import Channel, Server
from tests.fakes import FakeDiscordClient

BOT_MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "discord_mcp" / "bot.py"


def test_bot_delegates_to_injected_client():
    fake = FakeDiscordClient()
    fake.set_servers([Server(id="s1", name="guild")])
    fake.set_channels([Channel(id="c1", name="general")])

    bot = Bot(discord_client=fake)

    bot.get_servers()
    bot.get_channels("guild")

    assert fake.calls["get_servers"] == [None]
    assert fake.calls["get_channels"] == ["s1"]


def test_bot_accepts_real_discord_api_client_in_constructor():
    client = DiscordApiClient(base_url="https://example.invalid", headers={})

    bot = Bot(discord_client=client)

    assert isinstance(bot._client, DiscordApiClient)


def test_bot_module_does_not_import_requests():
    tree = ast.parse(BOT_MODULE_PATH.read_text(encoding="utf-8"))

    imported_modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    assert "requests" not in imported_modules
    assert not any(module.startswith("requests.") for module in imported_modules)


def test_bot_module_does_not_create_requests_session():
    tree = ast.parse(BOT_MODULE_PATH.read_text(encoding="utf-8"))

    session_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "Session"
    ]

    assert session_calls == []
