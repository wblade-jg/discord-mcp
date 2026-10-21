"""Property 5: la re-obtención de mensajes expirada fallida sirve la caché obsoleta.

Feature: bot-cache-behavior, Property 5: La re-obtención de mensajes expirada fallida sirve la caché obsoleta
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from discord_mcp.bot import Bot
from discord_mcp.models.discord_bot import Channel, Message, MessageBulk, Server
from tests.fakes import FakeDiscordClient, MutableClock, error_strategy


@given(
    error=error_strategy(),
    ttl=st.integers(min_value=1, max_value=60),
    overshoot=st.integers(min_value=0, max_value=120),
)
@settings(max_examples=100)
def test_failed_refetch_serves_stale(error, ttl, overshoot):
    clock = MutableClock()
    fake = FakeDiscordClient()
    stale = MessageBulk(
        messages=[Message(content="stale")],
        fetched_at=clock.now(),
        ttl=ttl,
    )
    channel = Channel(id="c1", name="general", messages=stale)
    fake.set_servers([Server(id="s1", name="guild", channels=[channel])])
    fake.set_messages(error)
    bot = Bot(discord_client=fake, clock=clock)
    bot.get_servers()
    bot.get_channels("guild")

    # expirar la caché: now - fetched_at >= ttl
    fetched_at = stale.fetched_at
    clock.advance(ttl + overshoot)

    result = bot.get_messages("guild", "general")

    # devuelve la obsoleta sin propagar
    assert result is stale
    assert result.messages[0].content == "stale"
    # la caché no se modifica con datos del fallo
    assert channel.messages is stale
    assert channel.messages.fetched_at == fetched_at
