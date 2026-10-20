"""Property 6: la resolución de nombre a id es correcta.

Feature: bot-cache-behavior, Property 6: La resolución de nombre a id es correcta
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from discord_mcp.bot import Bot
from discord_mcp.exceptions import NotFoundError
from discord_mcp.models.discord_bot import Channel, Server
from tests.fakes import FakeDiscordClient


def make_servers(names):
    return [Server(id=f"s-{i}", name=name) for i, name in enumerate(names)]


def make_channels(names):
    return [Channel(id=f"c-{i}", name=name) for i, name in enumerate(names)]


@given(
    names=st.lists(st.text(min_size=1, max_size=10), min_size=1, max_size=5),
    query=st.text(min_size=1, max_size=10),
)
@settings(max_examples=100)
def test_server_resolution_by_name(names, query):
    servers = make_servers(names)
    fake = FakeDiscordClient()
    fake.set_servers(servers)
    bot = Bot(discord_client=fake)
    bot.get_servers()

    if query in names:
        server = bot._resolve_server(query)
        # devuelve el servidor cuyo name coincide
        assert server.name == query
        assert server is servers[names.index(query)]
    else:
        with pytest.raises(NotFoundError) as exc_info:
            bot._resolve_server(query)
        assert exc_info.value.entity == "server"
        assert exc_info.value.name == query


@given(
    channel_names=st.lists(st.text(min_size=1, max_size=10), min_size=1, max_size=5),
    query=st.text(min_size=1, max_size=10),
)
@settings(max_examples=100)
def test_channel_resolution_by_name(channel_names, query):
    channels = make_channels(channel_names)
    server = Server(id="s1", name="guild", channels=channels)
    fake = FakeDiscordClient()
    fake.set_servers([server])
    bot = Bot(discord_client=fake)
    bot.get_servers()

    if query in channel_names:
        channel = bot._resolve_channel(server, query)
        assert channel.name == query
        assert channel is channels[channel_names.index(query)]
    else:
        with pytest.raises(NotFoundError) as exc_info:
            bot._resolve_channel(server, query)
        assert exc_info.value.entity == "channel"
        assert exc_info.value.name == query


@given(query=st.text(min_size=1, max_size=10))
@settings(max_examples=50)
def test_resolution_raises_when_prerequisite_cache_not_populated(query):
    # sin poblar servidores: get_channels y get_messages fallan
    bot = Bot(discord_client=FakeDiscordClient())

    with pytest.raises(NotFoundError) as exc_info:
        bot.get_channels(query)
    assert exc_info.value.entity == "server"

    with pytest.raises(NotFoundError) as exc_info:
        bot.get_messages(query, "general")
    assert exc_info.value.entity == "server"

    # servidores poblados pero canales sin poblar: get_messages falla
    fake = FakeDiscordClient()
    fake.set_servers([Server(id="s1", name="guild")])
    bot2 = Bot(discord_client=fake)
    bot2.get_servers()

    with pytest.raises(NotFoundError) as exc_info:
        bot2.get_messages("guild", query)
    assert exc_info.value.entity == "channel"
