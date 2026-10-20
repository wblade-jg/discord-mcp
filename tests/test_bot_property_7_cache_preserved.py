"""Property 7: el estado de la caché se preserva ante cualquier fallo.

Feature: bot-cache-behavior, Property 7: El estado de la caché se preserva ante cualquier fallo
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from discord_mcp.bot import Bot
from discord_mcp.exceptions import DiscordApiError, RateLimitExceeded
from discord_mcp.models.discord_bot import Channel, Message, MessageBulk, Server
from tests.fakes import FakeDiscordClient, MutableClock


def error_strategy():
    return st.sampled_from([DiscordApiError("boom"), RateLimitExceeded(1.0)])


@given(error=error_strategy(), fail_servers=st.booleans())
@settings(max_examples=100)
def test_servers_fetch_failure_preserves_none_cache(error, fail_servers):
    fake = FakeDiscordClient()
    bot = Bot(discord_client=fake)

    if fail_servers:
        fake.set_servers(error)
        try:
            bot.get_servers()
        except (DiscordApiError, RateLimitExceeded):
            pass
        assert bot._servers is None
    else:
        servers = [Server(id="s1", name="guild")]
        fake.set_servers(servers)
        assert bot.get_servers() == servers
        # éxitos posteriores no tocan la caché ya poblada
        fake.set_servers(error)
        assert bot.get_servers() == servers
        assert len(fake.calls["get_servers"]) == 1


@given(error=error_strategy(), populate_servers=st.booleans())
@settings(max_examples=100)
def test_channels_fetch_failure_preserves_none_channels(error, populate_servers):
    clock = MutableClock()
    fake = FakeDiscordClient()
    servers = [Server(id="s1", name="guild")]
    fake.set_servers(servers)
    fake.set_channels(error)
    bot = Bot(discord_client=fake, clock=clock)
    bot.get_servers()
    server = bot._resolve_server("guild")

    if populate_servers:
        # ya poblado: no se vuelve a llamar al cliente, no hay fallo posible
        fake.set_channels([])
        assert bot.get_channels("guild") == []
        assert bot.get_channels("guild") == []
        assert len(fake.calls["get_channels"]) == 1
    else:
        try:
            bot.get_channels("guild")
        except (DiscordApiError, RateLimitExceeded):
            pass
        assert server.channels is None


@given(error=error_strategy(), ttl=st.integers(min_value=1, max_value=60))
@settings(max_examples=100)
def test_messages_first_fetch_failure_preserves_none_messages(error, ttl):
    clock = MutableClock()
    fake = FakeDiscordClient()
    channel = Channel(id="c1", name="general")
    fake.set_servers([Server(id="s1", name="guild", channels=[channel])])
    fake.set_channels([channel])
    fake.set_messages(error)
    bot = Bot(discord_client=fake, clock=clock)
    bot.get_servers()
    bot.get_channels("guild")

    try:
        bot.get_messages("guild", "general")
    except (DiscordApiError, RateLimitExceeded):
        pass

    assert channel.messages is None


@given(error=error_strategy(), ttl=st.integers(min_value=1, max_value=60))
@settings(max_examples=100)
def test_messages_refetch_failure_preserves_stale_cache(error, ttl):
    clock = MutableClock()
    fake = FakeDiscordClient()
    stale = MessageBulk(
        messages=[Message(content="stale")],
        fetched_at=clock.now(),
        ttl=ttl,
    )
    channel = Channel(id="c1", name="general", messages=stale)
    fake.set_servers([Server(id="s1", name="guild", channels=[channel])])
    fake.set_channels([channel])
    fake.set_messages(error)
    bot = Bot(discord_client=fake, clock=clock)
    bot.get_servers()
    bot.get_channels("guild")

    fetched_at = stale.fetched_at
    clock.advance(ttl)
    result = bot.get_messages("guild", "general")

    assert result is stale
    assert channel.messages is stale
    assert channel.messages.fetched_at == fetched_at
