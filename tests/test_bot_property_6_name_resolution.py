"""Property 6: la resolución de nombre a id es correcta.

Feature: bot-cache-behavior, Property 6: La resolución de nombre a id es correcta

Solo se conserva la rama de prerrequisitos: resolver sobre una caché sin
poblar debe fallar con ``NotFoundError`` (no ``AttributeError``/``IndexError``).
La resolución positiva y el nombre inexistente ya los cubre ``test_bot.py``
por API pública.
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from discord_mcp.bot import Bot
from discord_mcp.exceptions import NotFoundError
from discord_mcp.models.discord_bot import Server
from tests.fakes import FakeDiscordClient


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
