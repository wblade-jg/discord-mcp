"""Tests de integración de las herramientas Discord con el ``McpServer``."""

import json

import pytest

from discord_mcp.bot import Bot
from discord_mcp.discord_tools import register_discord_tools
from discord_mcp.exceptions import DiscordApiError, RateLimitExceeded
from discord_mcp.models.discord_bot import Channel, Message, MessageBulk, Server
from discord_mcp.models.json_rpc import JsonRpcRequest
from discord_mcp.protocol_versions.mcp_2025_11_25 import Mcp20251125
from discord_mcp.protocol_versions.mcp_2026_07_28 import Mcp20260728
from discord_mcp.server import McpServer

PROTOCOLS = [Mcp20251125, Mcp20260728]


def build_server(protocol_cls, fake, clock):
    """Servidor con un protocolo, las tools Discord y la sesion inicializada."""
    server = McpServer()
    server.add_implementation_protocol(protocol_cls())
    register_discord_tools(server, Bot(discord_client=fake, clock=clock))
    request = JsonRpcRequest(
        id=0,
        jsonrpc="2.0",
        method="initialize",
        params={"protocolVersion": protocol_cls().protocol_version},
    )
    server.handle(request.model_dump())
    return server


def call_tool(mcp_server, name, arguments):
    request = JsonRpcRequest(
        id=1,
        jsonrpc="2.0",
        method="tools/call",
        params={"name": name, "arguments": arguments},
    )
    response = mcp_server.handle(request.model_dump())
    return json.loads(response)


@pytest.fixture(params=PROTOCOLS, ids=lambda cls: cls().protocol_version)
def protocol_server(request, fake, clock):
    return build_server(request.param, fake, clock)


@pytest.fixture
def mcp_server(fake, clock):
    return build_server(Mcp20260728, fake, clock)


def _tools_by_name(response):
    return {tool["name"]: tool for tool in response["result"]["tools"]}


# --- initialize / server/discover ------------------------------------------


def test_initialize_returns_protocol_capabilities_and_server_info():
    # Solo el protocolo 2025 expone `initialize`; el 2026 usa `server/discover`.
    server = McpServer()
    protocol = Mcp20251125()
    server.add_implementation_protocol(protocol)

    response = json.loads(
        server.handle(
            {
                "jsonrpc": "2.0",
                "id": 0,
                "method": "initialize",
                "params": {"protocolVersion": protocol.protocol_version},
            }
        )
    )

    assert response["id"] == 0
    assert response["result"]["protocolVersion"] == "2025-11-25"
    # sin tools registradas capabilities queda vacio
    assert response["result"]["capabilities"] == {}
    assert response["result"]["serverInfo"] == {
        "name": "discord-mcp",
        "version": "0.1.0",
    }


def test_server_discover_returns_versions_and_capabilities(mcp_server):
    response = json.loads(
        mcp_server.handle({"jsonrpc": "2.0", "id": 3, "method": "server/discover"})
    )

    result = response["result"]
    assert result["resultType"] == "complete"
    assert result["supportedVersions"] == ["2026-07-28"]
    assert result["capabilities"] == {"tools": {}}
    assert result["_meta"]["io.modelcontextprotocol/serverInfo"] == {
        "name": "discord-mcp",
        "version": "0.1.0",
    }


def test_unknown_method_returns_none(mcp_server):
    # Caracterizacion: el `match` de los routers no tiene `case _`; un metodo
    # desconocido no produce respuesta JSON-RPC.
    response = mcp_server.handle({"jsonrpc": "2.0", "id": 1, "method": "nope"})

    assert response is None


# --- tools/list ------------------------------------------------------------


@pytest.mark.parametrize(
    "protocol_cls", PROTOCOLS, ids=lambda cls: cls().protocol_version
)
def test_tools_list_returns_discord_tools_with_schema(protocol_cls, fake, clock):
    server = build_server(protocol_cls, fake, clock)

    response = json.loads(
        server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    )

    tools = _tools_by_name(response)
    assert set(tools) == {"get_servers", "get_channels", "get_messages"}
    # bot/clock son cierres: no aparecen en el esquema
    assert tools["get_servers"]["inputSchema"] == {
        "type": "object",
        "properties": {},
        "required": [],
    }
    assert set(tools["get_channels"]["inputSchema"]["properties"]) == {"server_name"}
    assert tools["get_channels"]["inputSchema"]["required"] == ["server_name"]
    assert set(tools["get_messages"]["inputSchema"]["properties"]) == {
        "server_name",
        "channel_name",
    }
    assert tools["get_messages"]["inputSchema"]["required"] == [
        "server_name",
        "channel_name",
    ]


def test_tools_list_includes_title_and_description(mcp_server):
    response = json.loads(
        mcp_server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    )

    tools = _tools_by_name(response)
    assert tools["get_servers"]["title"] == "Discord: List Servers"
    assert tools["get_servers"]["description"].startswith(
        "Lista los servidores (guilds) de Discord"
    )
    # la sección Args: no contamina la descripción; los params van al esquema
    assert tools["get_channels"]["description"] == (
        "Lista los canales de texto de un servidor de Discord."
    )


# --- tools/call: salida de texto -------------------------------------------


def test_get_servers_returns_formatted_text(mcp_server, fake):
    fake.set_servers([Server(id="s1", name="guild"), Server(id="s2", name="other")])

    result = call_tool(mcp_server, "get_servers", {})

    assert result["result"]["content"][0]["text"] == (
        "name: guild, id: s1\nname: other, id: s2"
    )
    assert "isError" not in result["result"]


def test_get_channels_returns_formatted_text(mcp_server, fake):
    fake.set_servers([Server(id="s1", name="guild")])
    fake.set_channels([Channel(id="c1", name="general", type=0)])
    call_tool(mcp_server, "get_servers", {})

    result = call_tool(mcp_server, "get_channels", {"server_name": "guild"})

    assert result["result"]["content"][0]["text"] == "name: general, id: c1"


def test_get_channels_excludes_non_text_channels(mcp_server, fake):
    fake.set_servers([Server(id="s1", name="guild")])
    fake.set_channels(
        [
            Channel(id="c1", name="general", type=0),
            Channel(id="c2", name="rules", type=0),
            Channel(id="c3", name="voice", type=2),
            Channel(id="c4", name="info", type=4),
        ]
    )
    call_tool(mcp_server, "get_servers", {})

    result = call_tool(mcp_server, "get_channels", {"server_name": "guild"})

    assert result["result"]["content"][0]["text"] == (
        "name: general, id: c1\nname: rules, id: c2"
    )


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


# --- tools/call: errores ---------------------------------------------------


def test_unknown_tool_returns_invalid_params_with_tool_name(protocol_server):
    result = call_tool(protocol_server, "does_not_exist", {})

    assert result["error"]["code"] == -32602
    assert result["data"]["Unknown tool"] == "does_not_exist"


def test_missing_arguments_return_invalid_params(protocol_server):
    result = call_tool(protocol_server, "get_channels", {})

    assert result["error"]["code"] == -32602
    assert result["data"]["message"]


def test_wrong_arguments_return_invalid_params(protocol_server):
    result = call_tool(
        protocol_server, "get_channels", {"server_name": "x", "unexpected": 1}
    )

    assert result["error"]["code"] == -32602
    assert result["data"]["message"]


@pytest.mark.parametrize(
    ("program", "expected_fragment"),
    [
        (lambda fake: fake.set_servers(DiscordApiError("boom")), "boom"),
        (lambda fake: fake.set_servers(RateLimitExceeded(2.5)), "2.5"),
        (lambda fake: fake.set_servers([]), None),
    ],
    ids=["api-error", "rate-limit", "not-found"],
)
def test_tool_errors_become_is_error_result(
    protocol_server, fake, expected_fragment, program
):
    program(fake)
    if expected_fragment is None:
        # NotFoundError: el servidor no existe en la caché
        result = call_tool(protocol_server, "get_channels", {"server_name": "nope"})
    else:
        result = call_tool(protocol_server, "get_servers", {})

    assert result["result"]["isError"] is True
    if expected_fragment is not None:
        assert expected_fragment in result["result"]["content"][0]["text"]
