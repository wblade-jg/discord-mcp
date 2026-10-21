import inspect
import json

import pytest

from discord_mcp.exceptions import ToolExecutionError, ToolNotFoundError
from discord_mcp.server import McpServer
from discord_mcp.tools import (
    ExecuteToolRequest,
    Parameter,
    Tool,
    doc_tool_parser,
    tool,
)


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
        mcp_server.execute_tool(
            ExecuteToolRequest(name="dummy", arguments={"value": "pepe"})
        )
        == "tu valor es: pepe"
    )


def test_execute_tool_not_found(mcp_server):
    with pytest.raises(ToolNotFoundError):
        mcp_server.execute_tool(ExecuteToolRequest(name="pepe", arguments={}))


def test_execute_tool_missing_arguments(mcp_server):
    with pytest.raises(TypeError):
        mcp_server.execute_tool(ExecuteToolRequest(name="dummy", arguments={}))

    with pytest.raises(TypeError):
        mcp_server.execute_tool(
            ExecuteToolRequest(name="dummy", arguments={"pepe": "pepe"})
        )


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


@pytest.mark.parametrize(
    ("py_type", "json_type"),
    [
        (int, "integer"),
        (float, "number"),
        (bool, "boolean"),
        (list, "string"),  # tipo sin mapeo: fallback a string
    ],
)
def test_parameter_to_schema_maps_python_types(py_type, json_type):
    parameter = Parameter("value", py_type, inspect.Parameter.empty, "desc")

    assert parameter.to_schema() == {"type": json_type, "description": "desc"}


# --- doc_tool_parser -------------------------------------------------------


def test_doc_tool_parser_unifies_description_and_parses_args():
    info = doc_tool_parser(
        "Descripción inicial.\n"
        "Segunda línea del párrafo.\n"
        "\n"
        "Args:\n"
        "    name: el nombre\n"
        "    count: cuántas veces\n"
    )

    assert info["description"] == "Descripción inicial. Segunda línea del párrafo."
    assert info["parameters"] == {
        "name": "el nombre",
        "count": "cuántas veces",
    }


def test_doc_tool_parser_without_args_section_returns_full_description():
    info = doc_tool_parser("Solo descripción.\nSin sección de parámetros.")

    assert info["description"] == "Solo descripción. Sin sección de parámetros."
    assert info["parameters"] == {}


@pytest.mark.parametrize(
    "doc",
    [
        # sin separador ":" → split(":") no puede desempaquetar
        "Descripción.\n\nArgs:\n    name sin separador\n",
        # con ":" de más → demasiados elementos para desempaquetar
        "Descripción.\n\nArgs:\n    name: desc: extra\n",
    ],
    ids=["sin-separador", "separador-extra"],
)
def test_doc_tool_parser_rejects_malformed_arg_lines(doc):
    with pytest.raises(ValueError):
        doc_tool_parser(doc)


def test_tool_decorator_requires_doc_entry_for_each_parameter():
    with pytest.raises(KeyError):

        @tool
        def poorly_documented(documented, undocumented):
            """Descripción.

            Args:
                documented: parámetro documentado
            """


def test_tool_decorator_builds_tool_with_title_description_and_parameters():
    @tool(title="Mi Tool")
    def my_tool(value: str):
        """Una descripción clara.

        Args:
            value: el valor de prueba
        """

    assert isinstance(my_tool, Tool)
    assert my_tool.title == "Mi Tool"
    assert my_tool.description == "Una descripción clara."
    assert my_tool.parameters["value"].description == "el valor de prueba"
