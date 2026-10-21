"""Property 4: la primera obtención de mensajes fallida propaga el error.

Feature: bot-cache-behavior, Property 4: La primera obtención de mensajes fallida propaga el error
"""

import pytest
from hypothesis import given, settings

from discord_mcp.bot import Bot
from discord_mcp.exceptions import DiscordApiError, RateLimitExceeded
from discord_mcp.models.discord_bot import Channel, Server
from tests.fakes import ApiError, FakeDiscordClient, error_strategy


@given(error=error_strategy())
@settings(max_examples=100)
def test_first_fetch_failure_propagates(error: ApiError):
    fake = FakeDiscordClient()
    channel = Channel(id="c1", name="general")
    fake.set_servers([Server(id="s1", name="guild", channels=[channel])])
    fake.set_messages(error)
    bot = Bot(discord_client=fake)
    bot.get_servers()
    bot.get_channels("guild")

    with pytest.raises((DiscordApiError, RateLimitExceeded)) as exc_info:
        bot.get_messages("guild", "general")

    assert exc_info.value is error
    assert len(fake.calls["get_messages"]) == 1
    # sin caché previa => no hay fallback; el canal queda sin mensajes
    assert channel.messages is None
