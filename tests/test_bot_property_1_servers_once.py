"""Property 1: los servidores se obtienen a lo sumo una vez.

Feature: bot-cache-behavior, Property 1: Los servidores se obtienen a lo sumo una vez
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from discord_mcp.bot import Bot
from discord_mcp.models.discord_bot import Server
from tests.fakes import FakeDiscordClient


def make_servers(names):
    return [Server(id=f"id-{i}", name=name) for i, name in enumerate(names)]


@given(
    server_names=st.lists(st.text(min_size=1, max_size=10), min_size=0, max_size=5),
    extra_calls=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=100)
def test_servers_fetched_at_most_once(server_names, extra_calls):
    fake = FakeDiscordClient()
    fake.set_servers(make_servers(server_names))
    bot = Bot(discord_client=fake)

    first = bot.get_servers()
    results = [bot.get_servers() for _ in range(extra_calls)]

    assert len(fake.calls["get_servers"]) == 1
    assert first == make_servers(server_names)
    assert all(result is first for result in results)
