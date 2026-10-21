"""Fixtures compartidas entre tests."""

import pytest

from discord_mcp.bot import Bot
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
