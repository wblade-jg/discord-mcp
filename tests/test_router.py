import pytest
from pydantic import ValidationError

from discord_mcp.exceptions import (
    MissingProtocolVersionError,
    NotSupportedProtocolError,
)
from discord_mcp.server import McpServer


class FakeProtocol:
    def __init__(self, protocol_version):
        self.protocol_version = protocol_version

    def router(self, request, mcp_server):
        return '{"ok": "' + self.protocol_version + '"}'

@pytest.fixture
def mcp_server():
    mcp_server = McpServer()
    mcp_server.add_implementation_protocol(FakeProtocol("2025-11-25"))
    mcp_server.add_implementation_protocol(FakeProtocol("2026-07-28"))
    return mcp_server

def test_resolve_protocol(mcp_server):
    mock = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25"}}

    assert '{"ok": "2025-11-25"}' == mcp_server.handle(mock)

def test_unavailable_protocol(mcp_server):
    mock = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2027-07-28"}}
    
    with pytest.raises(NotSupportedProtocolError):
        mcp_server.handle(mock)

def test_missing_protocol_version(mcp_server):
    mock = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    
    with pytest.raises(MissingProtocolVersionError):
        mcp_server.handle(mock)

def test_incorrect_jsonrpc_message(mcp_server):
    mock1 = {"method": "initialize", "params": {"protocolVersion": "2027-07-28"}}
    mock2 = {"id": 1, "params": {"protocolVersion": "2027-07-28"}}

    with pytest.raises(ValidationError):
        mcp_server.handle(mock1)
        mcp_server.handle(mock2)

