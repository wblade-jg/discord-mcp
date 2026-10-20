"""Property 2: los canales se obtienen a lo sumo una vez por servidor.

Feature: bot-cache-behavior, Property 2: Los canales se obtienen a lo sumo una vez por servidor
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from discord_mcp.bot import Bot
from discord_mcp.models.discord_bot import Channel, Server
from tests.fakes import FakeDiscordClient


def make_servers(names):
    return [Server(id=f"id-{i}", name=name) for i, name in enumerate(names)]


def make_channels(names):
    return [Channel(id=f"c-{i}", name=name) for i, name in enumerate(names)]


@given(
    server_name=st.text(min_size=1, max_size=10),
    channel_names=st.lists(st.text(min_size=1, max_size=10), min_size=0, max_size=5),
    extra_calls=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=100)
def test_channels_fetched_at_most_once_per_server(
    server_name, channel_names, extra_calls
):
    fake = FakeDiscordClient()
    servers = make_servers([server_name])
    fake.set_servers(servers)
    fake.set_channels(make_channels(channel_names))
    bot = Bot(discord_client=fake)
    bot.get_servers()

    first = bot.get_channels(server_name)
    results = [bot.get_channels(server_name) for _ in range(extra_calls)]

    assert len(fake.calls["get_channels"]) == 1
    assert fake.calls["get_channels"][0] == servers[0].id
    assert first == make_channels(channel_names)
    assert all(result is first for result in results)


@given(
    server_names=st.lists(
        st.text(min_size=1, max_size=10), min_size=2, max_size=5, unique=True
    )
)
@settings(max_examples=50)
def test_channels_fetched_once_per_distinct_server(server_names):
    fake = FakeDiscordClient()
    fake.set_servers(make_servers(server_names))
    fake.set_channels([])
    bot = Bot(discord_client=fake)
    bot.get_servers()

    for name in server_names:
        bot.get_channels(name)
        bot.get_channels(name)

    distinct_ids = {f"id-{i}" for i in range(len(server_names))}
    assert set(fake.calls["get_channels"]) == distinct_ids
    assert len(fake.calls["get_channels"]) == len(distinct_ids)
