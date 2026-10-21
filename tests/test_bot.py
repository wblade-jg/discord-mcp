"""Tests unitarios del ``Bot`` con ``FakeDiscordClient`` y reloj controlable."""

import pytest

from discord_mcp.bot import Bot
from discord_mcp.exceptions import DiscordApiError, NotFoundError, RateLimitExceeded
from discord_mcp.models.discord_bot import Channel, Message, MessageBulk, Server
from tests.fakes import FakeDiscordClient, MutableClock


@pytest.fixture
def fake():
    return FakeDiscordClient()


@pytest.fixture
def clock():
    return MutableClock()


@pytest.fixture
def bot(fake, clock):
    return Bot(discord_client=fake, clock=clock)


def make_server(server_id="s1", name="guild", channels=None):
    return Server(id=server_id, name=name, channels=channels)


def make_channel(channel_id="c1", name="general", messages=None):
    return Channel(id=channel_id, name=name, messages=messages)


def make_bulk(content="hola", ttl=5, fetched_at=None):
    return MessageBulk(
        messages=[Message(content=content)],
        fetched_at=fetched_at,
        ttl=ttl,
    )


# --- Servidores -----------------------------------------------------------


def test_first_fetch_populates_servers(bot, fake):
    fake.set_servers([make_server()])

    result = bot.get_servers()

    assert result == [make_server()]
    assert len(fake.calls["get_servers"]) == 1


def test_servers_served_from_cache_after_first_fetch(bot, fake):
    fake.set_servers([make_server()])

    first = bot.get_servers()
    second = bot.get_servers()

    assert first is second
    assert len(fake.calls["get_servers"]) == 1


def test_empty_servers_list_counts_as_populated(bot, fake):
    fake.set_servers([])

    assert bot.get_servers() == []
    assert bot.get_servers() == []
    assert len(fake.calls["get_servers"]) == 1


def test_first_servers_fetch_failure_propagates_and_cache_stays_none(bot, fake):
    fake.set_servers(DiscordApiError("boom"))

    with pytest.raises(DiscordApiError):
        bot.get_servers()

    assert bot._servers is None


# --- Canales --------------------------------------------------------------


def test_channels_resolved_by_server_name_and_cached(bot, fake):
    fake.set_servers([make_server()])
    fake.set_channels([make_channel()])
    bot.get_servers()

    result = bot.get_channels("guild")

    assert result == [make_channel()]
    assert fake.calls["get_channels"] == ["s1"]


def test_channels_served_from_cache_on_second_call(bot, fake):
    fake.set_servers([make_server()])
    fake.set_channels([make_channel()])
    bot.get_servers()

    bot.get_channels("guild")
    bot.get_channels("guild")

    assert len(fake.calls["get_channels"]) == 1


def test_empty_channels_list_counts_as_populated(bot, fake):
    fake.set_servers([make_server()])
    fake.set_channels([])
    bot.get_servers()

    assert bot.get_channels("guild") == []
    assert bot.get_channels("guild") == []
    assert len(fake.calls["get_channels"]) == 1


def test_unknown_server_raises_not_found(bot):
    with pytest.raises(NotFoundError) as exc_info:
        bot.get_channels("nope")

    assert exc_info.value.entity == "server"
    assert exc_info.value.name == "nope"


def test_first_channels_fetch_failure_propagates(bot, fake):
    fake.set_servers([make_server()])
    fake.set_channels(DiscordApiError("boom"))
    bot.get_servers()

    with pytest.raises(DiscordApiError):
        bot.get_channels("guild")

    assert bot.get_servers()[0].channels is None


def test_channels_only_include_text_type_and_cache_is_filtered(bot, fake):
    fake.set_servers([make_server()])
    fake.set_channels(
        [
            Channel(id="c1", name="general", type=0),
            Channel(id="c2", name="voice", type=2),
            Channel(id="c3", name="info", type=4),
        ]
    )
    bot.get_servers()

    first = bot.get_channels("guild")
    second = bot.get_channels("guild")

    assert [c.name for c in first] == ["general"]
    assert first is second
    assert len(fake.calls["get_channels"]) == 1
    assert [c.name for c in bot.get_servers()[0].channels] == ["general"]


# --- Mensajes -------------------------------------------------------------


def populated_bot(fake, clock, bulk):
    fake.set_servers([make_server(channels=[make_channel(messages=bulk)])])
    fake.set_channels([make_channel(messages=bulk)])
    bot = Bot(discord_client=fake, clock=clock)
    bot.get_servers()
    bot.get_channels("guild")
    return bot


def test_first_messages_fetch_sets_fetched_at_and_caches(bot, fake, clock):
    fake.set_servers([make_server()])
    fake.set_channels([make_channel()])
    fresh = make_bulk()
    fake.set_messages(fresh)
    bot.get_servers()
    bot.get_channels("guild")

    result = bot.get_messages("guild", "general")

    assert result is fresh
    assert result.fetched_at == clock.now()
    assert fake.calls["get_messages"] == ["c1"]


def test_valid_cache_served_without_client_call(fake, clock):
    cached = make_bulk(fetched_at=clock.now())
    bot = populated_bot(fake, clock, cached)

    result = bot.get_messages("guild", "general")

    assert result is cached
    assert fake.calls["get_messages"] == []


def test_expired_cache_triggers_refetch(fake, clock):
    cached = make_bulk(ttl=5, fetched_at=clock.now())
    bot = populated_bot(fake, clock, cached)
    fresh = make_bulk(content="nuevo")
    fake.set_messages(fresh)

    clock.advance(5)

    result = bot.get_messages("guild", "general")

    assert result is fresh
    assert result.fetched_at == clock.now()
    assert fake.calls["get_messages"] == ["c1"]


def test_unknown_channel_raises_not_found(bot, fake):
    fake.set_servers([make_server()])
    fake.set_channels([])
    bot.get_servers()
    bot.get_channels("guild")

    with pytest.raises(NotFoundError) as exc_info:
        bot.get_messages("guild", "missing")

    assert exc_info.value.entity == "channel"
    assert exc_info.value.name == "missing"


def test_first_messages_fetch_failure_propagates(bot, fake):
    fake.set_servers([make_server()])
    fake.set_channels([make_channel()])
    fake.set_messages(RateLimitExceeded(1.0))
    bot.get_servers()
    bot.get_channels("guild")

    with pytest.raises(RateLimitExceeded):
        bot.get_messages("guild", "general")


def test_failed_refetch_serves_stale_cache(fake, clock):
    stale = make_bulk(content="viejo", ttl=5, fetched_at=clock.now())
    bot = populated_bot(fake, clock, stale)
    fake.set_messages(DiscordApiError("boom"))

    clock.advance(10)

    result = bot.get_messages("guild", "general")

    assert result is stale
    assert result.messages[0].content == "viejo"
