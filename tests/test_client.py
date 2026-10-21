import pytest
import requests

import discord_mcp.discord_api as api_module
from discord_mcp.discord_api import DiscordApiClient, ResilientClientWrapper
from discord_mcp.exceptions import DiscordApiError, RateLimitExceeded


class FakeResponse:
    def __init__(self, status=200, json_data=None, headers=None):
        self.status_code = status
        self._json = json_data if json_data is not None else {}
        self.headers = headers or {}

    def json(self):
        return self._json

    def raise_for_status(self):
        if 400 <= self.status_code < 600:
            error = requests.exceptions.HTTPError(f"HTTP {self.status_code}")
            error.response = self
            raise error


class ScriptedClient:
    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def get(self, url, timeout=4):
        self.calls.append({"url": url, "timeout": timeout})
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
def no_sleep(monkeypatch):
    slept = []
    monkeypatch.setattr(api_module.time, "sleep", lambda s: slept.append(s))
    # Backoff determinista: siempre 0.5s en vez de aleatorio.
    monkeypatch.setattr(api_module.random, "uniform", lambda a, b: 0.5)
    return slept


def test_success_first_try_no_sleep(no_sleep):
    client = ScriptedClient([FakeResponse(200, json_data=[{"id": "1"}])])
    wrapper = ResilientClientWrapper(client)

    response = wrapper.get("https://x/guilds", timeout=4)

    assert response.status_code == 200
    assert len(client.calls) == 1
    assert client.calls[0]["timeout"] == 4
    assert no_sleep == []


def test_retry_on_503_then_success(no_sleep):
    client = ScriptedClient([FakeResponse(503), FakeResponse(503), FakeResponse(200)])
    wrapper = ResilientClientWrapper(client, max_retries=3)

    response = wrapper.get("https://x/guilds")

    assert response.status_code == 200
    assert len(client.calls) == 3
    assert no_sleep == [0.5, 0.5]


@pytest.mark.parametrize(
    "error",
    [
        requests.exceptions.ConnectionError("boom"),
        requests.exceptions.Timeout("slow"),
    ],
    ids=["connection-error", "timeout"],
)
def test_retry_on_connection_errors_then_success(no_sleep, error):
    client = ScriptedClient([error, FakeResponse(200)])
    wrapper = ResilientClientWrapper(client)

    response = wrapper.get("https://x/guilds")

    assert response.status_code == 200
    assert len(client.calls) == 2
    assert no_sleep == [0.5]


def test_429_respects_retry_after_header(no_sleep):
    client = ScriptedClient(
        [
            FakeResponse(429, json_data={}, headers={"Retry-After": "2"}),
            FakeResponse(200),
        ]
    )
    wrapper = ResilientClientWrapper(client)

    response = wrapper.get("https://x/guilds")

    assert response.status_code == 200
    assert no_sleep == [2.0]


def test_429_too_long_raises_rate_limit_exceeded(no_sleep):
    client = ScriptedClient(
        [FakeResponse(429, json_data={}, headers={"Retry-After": "30"})]
    )
    wrapper = ResilientClientWrapper(client, max_retries=3)

    with pytest.raises(RateLimitExceeded) as exc_info:
        wrapper.get("https://x/guilds")

    assert exc_info.value.retry_after == 30.0
    assert len(client.calls) == 1
    assert no_sleep == []


def test_401_fails_fast_with_invalid_token_message(no_sleep):
    client = ScriptedClient([FakeResponse(401), FakeResponse(200)])
    wrapper = ResilientClientWrapper(client)

    with pytest.raises(DiscordApiError, match="valid, unexpired bot token"):
        wrapper.get("https://x/guilds")

    assert len(client.calls) == 1
    assert no_sleep == []


def test_non_retryable_status_fails_fast(no_sleep):
    client = ScriptedClient([FakeResponse(404), FakeResponse(200)])
    wrapper = ResilientClientWrapper(client)

    with pytest.raises(DiscordApiError, match="404"):
        wrapper.get("https://x/guilds")

    assert len(client.calls) == 1
    assert no_sleep == []


def test_429_exhausting_retries_with_short_wait_raises_api_error(no_sleep):
    # 429 con espera corta: al agotar reintentos -> DiscordApiError, no RateLimitExceeded
    client = ScriptedClient([FakeResponse(429, headers={"Retry-After": "2"})] * 5)
    wrapper = ResilientClientWrapper(client, max_retries=3)

    with pytest.raises(DiscordApiError):
        wrapper.get("https://x/guilds")

    assert len(client.calls) == 4
    assert no_sleep == [2.0, 2.0, 2.0]


@pytest.mark.parametrize("header_value", [None, "not-a-number"])
def test_429_falls_back_to_backoff_when_retry_after_invalid(no_sleep, header_value):
    headers = {} if header_value is None else {"Retry-After": header_value}
    client = ScriptedClient([FakeResponse(429, headers=headers), FakeResponse(200)])
    wrapper = ResilientClientWrapper(client)

    response = wrapper.get("https://x/guilds")

    assert response.status_code == 200
    # backoff stubado: uniform siempre devuelve 0.5
    assert no_sleep == [0.5]


def test_exhausts_retries_raises_discord_api_error(no_sleep):
    client = ScriptedClient([FakeResponse(503)] * 5)
    wrapper = ResilientClientWrapper(client, max_retries=3)

    with pytest.raises(DiscordApiError):
        wrapper.get("https://x/guilds")

    # 1 intento inicial + 3 reintentos
    assert len(client.calls) == 4
    assert no_sleep == [0.5, 0.5, 0.5]


def test_get_channels_parses_type_field(no_sleep):
    payload = [
        {"id": "c1", "name": "general", "type": 0},
        {"id": "c2", "name": "info", "type": 4},
    ]
    client = ScriptedClient([FakeResponse(200, json_data=payload)])
    api = DiscordApiClient(base_url="https://x/api/v10", headers={})
    api.http_client = client

    channels = api.get_channels("s1")

    assert [(c.name, c.type) for c in channels] == [("general", 0), ("info", 4)]
