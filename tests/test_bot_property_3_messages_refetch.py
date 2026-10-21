"""Property 3: los mensajes se re-obtienen si y solo si la caché está ausente o expirada.

Feature: bot-cache-behavior, Property 3: Los mensajes se re-obtienen si y solo si la caché está ausente o expirada
"""

from datetime import datetime, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from discord_mcp.bot import Bot
from discord_mcp.models.discord_bot import Channel, Message, MessageBulk, Server
from tests.fakes import FakeDiscordClient, MutableClock

T0 = datetime(2024, 1, 1, tzinfo=timezone.utc)


def populated_bot(fake, clock, messages, fetched_at, ttl):
    bulk = (
        None
        if messages is None
        else MessageBulk(messages=messages, fetched_at=fetched_at, ttl=ttl)
    )
    channel = Channel(id="c1", name="general", messages=bulk)
    fake.set_servers([Server(id="s1", name="guild", channels=[channel])])
    fake.set_messages(MessageBulk(messages=[Message(content="fresh")]))
    bot = Bot(discord_client=fake, clock=clock)
    bot.get_servers()
    bot.get_channels("guild")
    return bot


@given(
    has_messages=st.booleans(),
    has_fetched_at=st.booleans(),
    ttl=st.integers(min_value=1, max_value=60),
    age_seconds=st.integers(min_value=0, max_value=120),
)
@settings(max_examples=100)
def test_refetch_iff_absent_or_expired(has_messages, has_fetched_at, ttl, age_seconds):
    clock = MutableClock(start=T0)
    fake = FakeDiscordClient()
    messages = [Message(content="cached")] if has_messages else None
    fetched_at = T0 if has_fetched_at else None
    bot = populated_bot(fake, clock, messages, fetched_at, ttl)

    clock.advance(age_seconds)
    bot.get_messages("guild", "general")

    cache_valid = has_messages and has_fetched_at and age_seconds < ttl
    expected_calls = 0 if cache_valid else 1
    assert len(fake.calls["get_messages"]) == expected_calls


@given(ttl=st.integers(min_value=1, max_value=60))
@settings(max_examples=20)
def test_ttl_boundary_exactly_equal_is_expired(ttl):
    clock = MutableClock(start=T0)
    fake = FakeDiscordClient()
    bot = populated_bot(
        fake,
        clock,
        [Message(content="cached")],
        T0,
        ttl,
    )

    clock.advance(ttl)
    bot.get_messages("guild", "general")

    # now - fetched_at == ttl => expirada (frontera inclusiva en >=)
    assert len(fake.calls["get_messages"]) == 1
