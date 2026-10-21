"""Tests del ``McpServer``: dispatch de protocolo y frontera stdio (``run``)."""

import io
import json
import sys

import pytest
from pydantic import ValidationError

from discord_mcp.exceptions import (
    MissingProtocolVersionError,
    NotSupportedProtocolError,
)
from discord_mcp.models.json_rpc import JsonRpcRequest
from discord_mcp.server import McpServer


class FakeProtocol:
    def __init__(self, protocol_version):
        self.protocol_version = protocol_version

    def router(self, request, mcp_server):
        return json.dumps({"ok": self.protocol_version})


@pytest.fixture
def mcp_server():
    mcp_server = McpServer()
    mcp_server.add_implementation_protocol(FakeProtocol("2025-11-25"))
    mcp_server.add_implementation_protocol(FakeProtocol("2026-07-28"))
    return mcp_server


def run_lines(mcp_server, *lines, monkeypatch, capsys):
    """Ejecuta ``run()`` con ``lines`` como stdin y devuelve las respuestas."""
    monkeypatch.setattr(sys, "stdin", io.StringIO("\n".join(lines) + "\n"))
    mcp_server.run()
    return [json.loads(out) for out in capsys.readouterr().out.splitlines()]


def test_resolve_protocol(mcp_server):
    mock = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2025-11-25"},
    }

    assert json.loads(mcp_server.handle(mock)) == {"ok": "2025-11-25"}


def test_unavailable_protocol(mcp_server):
    mock = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2027-07-28"},
    }

    with pytest.raises(NotSupportedProtocolError):
        mcp_server.handle(mock)


@pytest.mark.parametrize(
    "mock",
    [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    ],
    ids=["params-vacio", "sin-params"],
)
def test_missing_protocol_version(mcp_server, mock):
    with pytest.raises(MissingProtocolVersionError):
        mcp_server.handle(mock)


def test_json_rpc_request_without_params_defaults_to_empty_dict():
    request = JsonRpcRequest(jsonrpc="2.0", id=1, method="tools/list")

    assert request.params == {}


@pytest.mark.parametrize(
    "mock",
    [
        {"method": "initialize", "params": {"protocolVersion": "2027-07-28"}},
        {"id": 1, "params": {"protocolVersion": "2027-07-28"}},
    ],
    ids=["sin-jsonrpc-e-id", "sin-jsonrpc-y-method"],
)
def test_incorrect_jsonrpc_message(mcp_server, mock):
    with pytest.raises(ValidationError):
        mcp_server.handle(mock)


# --- run(): frontera stdio ------------------------------------------------


def test_run_resolves_protocol_and_keeps_serving(mcp_server, monkeypatch, capsys):
    first = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2026-07-28"},
        }
    )
    second = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "initialize",
            "params": {"protocolVersion": "2026-07-28"},
        }
    )

    responses = run_lines(
        mcp_server, first, second, monkeypatch=monkeypatch, capsys=capsys
    )

    assert responses == [{"ok": "2026-07-28"}, {"ok": "2026-07-28"}]


def test_run_session_protocol_fixed_after_first_request(
    mcp_server, monkeypatch, capsys
):
    # La sesion se fija con la 1a peticion; la 2a pide otra version y se ignora.
    first = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-11-25"},
        }
    )
    second = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "initialize",
            "params": {"protocolVersion": "2026-07-28"},
        }
    )

    responses = run_lines(
        mcp_server, first, second, monkeypatch=monkeypatch, capsys=capsys
    )

    assert responses == [{"ok": "2025-11-25"}, {"ok": "2025-11-25"}]


@pytest.mark.parametrize(
    "line",
    [
        "{oops",
        '["x"]',
        "null",
        '"s"',
        "42",
    ],
    ids=["json-malformado", "lista", "null", "cadena", "numero"],
)
def test_run_invalid_input_returns_parse_error(mcp_server, monkeypatch, capsys, line):
    responses = run_lines(mcp_server, line, monkeypatch=monkeypatch, capsys=capsys)

    assert responses == [
        {
            "jsonrpc": "2.0",
            "id": None,
            "error": {"code": -32600, "message": "Invalid request"},
            "data": None,
        }
    ]


def test_run_unsupported_protocol_returns_invalid_params(
    mcp_server, monkeypatch, capsys
):
    line = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "initialize",
            "params": {"protocolVersion": "2027-07-28"},
        }
    )

    (response,) = run_lines(mcp_server, line, monkeypatch=monkeypatch, capsys=capsys)

    assert response["id"] == 7
    assert response["error"]["code"] == -32602
    assert response["data"]["message"] == "Unavailable protocol"
    assert response["data"]["supportedVersions"] == ["2025-11-25", "2026-07-28"]


def test_run_missing_protocol_version_returns_invalid_params(
    mcp_server, monkeypatch, capsys
):
    line = json.dumps({"jsonrpc": "2.0", "id": 7, "method": "initialize", "params": {}})

    (response,) = run_lines(mcp_server, line, monkeypatch=monkeypatch, capsys=capsys)

    assert response["id"] == 7
    assert response["error"]["code"] == -32602
    assert response["data"]["message"] == "Missing protocol version in request"


def test_run_validation_error_with_id(mcp_server, monkeypatch, capsys):
    line = json.dumps({"jsonrpc": "2.0", "id": 7, "method": "initialize"})

    (response,) = run_lines(mcp_server, line, monkeypatch=monkeypatch, capsys=capsys)

    assert response["id"] == 7
    assert response["error"]["code"] == -32602


def test_run_validation_error_without_id(mcp_server, monkeypatch, capsys):
    line = json.dumps({"jsonrpc": "2.0", "method": "initialize"})

    (response,) = run_lines(mcp_server, line, monkeypatch=monkeypatch, capsys=capsys)

    assert response["id"] is None
    assert response["error"]["code"] == -32602


def test_run_keeps_serving_after_error_line(mcp_server, monkeypatch, capsys):
    bad = "{oops"
    good = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2026-07-28"},
        }
    )

    responses = run_lines(mcp_server, bad, good, monkeypatch=monkeypatch, capsys=capsys)

    assert responses[0]["error"]["code"] == -32600
    assert responses[1] == {"ok": "2026-07-28"}
