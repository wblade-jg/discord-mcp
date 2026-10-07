import inspect
import json

import pytest

from discord_mcp.exceptions import ToolExecutionError, ToolNotFoundError
from discord_mcp.server import McpServer
from discord_mcp.tools import ExecuteToolRequest, Parameter, Tool


def dummy(value):
    return f"tu valor es: {value}"


def failfast():
    raise ToolExecutionError("Error Generico")


@pytest.fixture
def mcp_server():
    mcp_server = McpServer()
    mcp_server.add_tool(
        Tool(
            "dummy",
            "funcion de prueba",
            parameters=[Parameter("value", str, "hola", "parametro de prueba")],
            function=dummy,
        )
    )

    mcp_server.add_tool(
        Tool(
            "failfast",
            "Esta funcion falla",
            function=failfast,
        )
    )
    return mcp_server


def test_execute_tool(mcp_server):
    assert (
        mcp_server.execute_tool(ExecuteToolRequest(name="dummy", arguments={"value": "pepe"}))
        == "tu valor es: pepe"
    )


def test_execute_tool_not_found(mcp_server):
    with pytest.raises(ToolNotFoundError):
        mcp_server.execute_tool(ExecuteToolRequest(name="pepe", arguments={}))


def test_execute_tool_missing_arguments(mcp_server):
    with pytest.raises(TypeError):
        mcp_server.execute_tool(ExecuteToolRequest(name="dummy", arguments={}))
    
    with pytest.raises(TypeError):
        mcp_server.execute_tool(ExecuteToolRequest(name="dummy", arguments={"pepe": "pepe"}))


def test_execute_tool_internal_error(mcp_server):
    with pytest.raises(ToolExecutionError):
        mcp_server.execute_tool(ExecuteToolRequest(name="failfast", arguments={}))


def test_tool_to_dict_is_json_serializable():
    tool = Tool(
        "dummy",
        "funcion de prueba",
        parameters=[
            Parameter("value", str, inspect.Parameter.empty, "parametro de prueba")
        ],
        function=dummy,
    )
    schema = tool.to_dict()
    json.dumps(schema)
    assert schema["name"] == "dummy"
    assert schema["inputSchema"]["properties"] == {
        "value": {"type": "string", "description": "parametro de prueba"}
    }
    assert schema["inputSchema"]["required"] == ["value"]


def test_tool_to_dict_excludes_defaulted_parameters_from_required():
    tool = Tool(
        "dummy",
        "funcion de prueba",
        parameters=[Parameter("value", str, "hola", "parametro de prueba")],
        function=dummy,
    )
    assert tool.to_dict()["inputSchema"]["required"] == []
