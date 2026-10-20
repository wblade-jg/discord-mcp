"""Tests de integración de las herramientas Discord con el ``McpServer``."""

import json

import pytest

from discord_mcp.bot import Bot
from discord_mcp.discord_tools import register_discord_tools
from discord_mcp.exceptions import (
    DiscordApiError,
    RateLimitExceeded,
    ToolExecutionError,
)
from discord_mcp.models.discord_bot import Channel, Message, MessageBulk, Server
from discord_mcp.models.json_rpc import JsonRpcRequest
from discord_mcp.protocol_versions.mcp_2025_11_25 import Mcp20251125
from discord_mcp.protocol_versions.mcp_2026_07_28 import Mcp20260728
from discord_mcp.server import McpServer
from tests.fakes import FakeDiscordClient, MutableClock


@pytest.fixture
def fake():
    return FakeDiscordClient()


@pytest.fixture
def clock():
    return MutableClock()


@pytest.fixture
def mcp_server(fake, clock):
    server = McpServer()
    server.add_implementation_protocol(Mcp20260728())
    register_discord_tools(server, Bot(discord_client=fake, clock=clock))
    initialize(server)
    return server


def initialize(mcp_server):
    request = JsonRpcRequest(
        id=0,
        jsonrpc="2.0",
        method="initialize",
        params={"protocolVersion": "2026-07-28"},
    )
    mcp_server.handle(request.model_dump())


def call_tool(mcp_server, name, arguments):
    request = JsonRpcRequest(
        id=1,
        jsonrpc="2.0",
        method="tools/call",
        params={"name": name, "arguments": arguments},
    )
    response = mcp_server.handle(request.model_dump())
    return json.loads(response)


def test_tools_list_exposes_discord_tools(mcp_server):
    tools = mcp_server.get_tools()

    assert set(tools) == {"get_servers", "get_channels", "get_messages"}
    assert set(tools["get_channels"].parameters) == {"server_name"}
    assert set(tools["get_messages"].parameters) == {"server_name", "channel_name"}
    # bot/clock son cierres: no aparecen en el esquema
    assert tools["get_servers"].parameters == {}


def _tool_names(response):
    return {tool["name"] for tool in response["result"]["tools"]}


def test_tools_list_without_params_returns_tools(mcp_server):
    response = json.loads(
        mcp_server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    )

    assert _tool_names(response) == {"get_servers", "get_channels", "get_messages"}


def test_tools_list_without_params_returns_tools_on_2025_protocol(fake, clock):
    server = McpServer()
    server.add_implementation_protocol(Mcp20251125())
    register_discord_tools(server, Bot(discord_client=fake, clock=clock))
    server.handle(
        {
            "jsonrpc": "2.0",
            "id": 0,
            "method": "initialize",
            "params": {"protocolVersion": "2025-11-25"},
        }
    )

    response = json.loads(
        server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    )

    assert _tool_names(response) == {"get_servers", "get_channels", "get_messages"}


def test_get_servers_returns_formatted_text(mcp_server, fake):
    fake.set_servers([Server(id="s1", name="guild"), Server(id="s2", name="other")])

    result = call_tool(mcp_server, "get_servers", {})

    assert result["result"]["content"][0]["text"] == "guild (s1), other (s2)"
    assert "isError" not in result["result"]


def test_get_channels_returns_formatted_text(mcp_server, fake):
    fake.set_servers([Server(id="s1", name="guild")])
    fake.set_channels([Channel(id="c1", name="general")])
    call_tool(mcp_server, "get_servers", {})

    result = call_tool(mcp_server, "get_channels", {"server_name": "guild"})

    assert result["result"]["content"][0]["text"] == "general (c1)"


def test_get_messages_returns_joined_contents(mcp_server, fake):
    fake.set_servers([Server(id="s1", name="guild")])
    fake.set_channels([Channel(id="c1", name="general")])
    fake.set_messages(
        MessageBulk(
            messages=[Message(content="hola"), Message(content="adios")],
            fetched_at=None,
        )
    )
    call_tool(mcp_server, "get_servers", {})
    call_tool(mcp_server, "get_channels", {"server_name": "guild"})

    result = call_tool(
        mcp_server, "get_messages", {"server_name": "guild", "channel_name": "general"}
    )

    assert result["result"]["content"][0]["text"] == "hola\nadios"


def test_not_found_error_becomes_tool_execution_error(mcp_server):
    result = call_tool(mcp_server, "get_channels", {"server_name": "nope"})

    assert result["result"]["isError"] is True
    assert "nope" in result["result"]["content"][0]["text"]


def test_discord_api_error_becomes_tool_execution_error(mcp_server, fake):
    fake.set_servers(DiscordApiError("boom"))

    result = call_tool(mcp_server, "get_servers", {})

    assert result["result"]["isError"] is True
    assert "boom" in result["result"]["content"][0]["text"]


def test_rate_limit_error_becomes_tool_execution_error(mcp_server, fake):
    fake.set_servers(RateLimitExceeded(2.5))

    result = call_tool(mcp_server, "get_servers", {})

    assert result["result"]["isError"] is True


def test_unknown_tool_returns_json_rpc_error(mcp_server):
    result = call_tool(mcp_server, "does_not_exist", {})

    assert result["error"]["code"] == -32602


def test_bot_exception_wrapped_by_tool_execute(fake):
    server = McpServer()
    register_discord_tools(server, Bot(discord_client=fake))

    fake.set_servers(DiscordApiError("boom"))

    with pytest.raises(ToolExecutionError):
        server.get_tool("get_servers").execute({})

    with pytest.raises(ToolExecutionError):
        server.get_tool("get_channels").execute({"server_name": "nope"})
