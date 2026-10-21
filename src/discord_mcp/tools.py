import inspect
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from discord_mcp.exceptions import ToolExecutionError


class ExecuteToolRequest(BaseModel):
    name: str
    arguments: dict


_PYTHON_TO_JSON_SCHEMA = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
}


class Parameter:
    def __init__(self, name, kind, default, description):
        self.name = name
        self.type = kind
        self.default = default
        self.description = description

    def to_schema(self):
        return {
            "type": _PYTHON_TO_JSON_SCHEMA.get(self.type, "string"),
            "description": self.description,
        }

    def is_required(self):
        return self.default is inspect.Parameter.empty


class Tool:
    def __init__(
        self,
        name: str,
        description: str,
        function: Callable[..., Any],
        title="",
        parameters: list[Parameter] | None = None,
    ):
        self.name = name
        self.title = title
        self.description = description
        self.parameters = {
            parameter.name: parameter for parameter in (parameters or [])
        }
        self.function = function

    def to_dict(self):
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "inputSchema": {
                "type": "object",
                "properties": {
                    name: parameter.to_schema()
                    for name, parameter in self.parameters.items()
                },
                "required": [
                    name
                    for name, parameter in self.parameters.items()
                    if parameter.is_required()
                ],
            },
        }

    def execute(self, kwargs: dict[str, Any]):
        sig = inspect.signature(self.function)
        sig.bind(**kwargs)

        try:
            return self.function(**kwargs)
        except Exception as e:  # frontera: toda excepción de tool → ToolExecutionError
            raise ToolExecutionError(str(e)) from e


def doc_tool_parser(doc: str):
    info = {}
    info["description"] = ""
    info["parameters"] = {}

    lines = doc.splitlines()

    args_position = None
    for line in lines:
        if line.startswith("Args:"):
            args_position = lines.index(line)
            break

    # La descripción es todo el párrafo inicial hasta "Args:" (o el final),
    # unido en una sola línea para el cliente MCP.
    description_end = args_position if args_position is not None else len(lines)
    info["description"] = " ".join(
        line.strip() for line in lines[:description_end] if line.strip()
    )

    if args_position is not None:
        for line in lines[args_position + 1 :]:
            param_name, param_description = line.split(":")
            info["parameters"].update({param_name.strip(): param_description.strip()})

    return info


def tool(func=None, *, title=""):
    def build(target):
        name = target.__name__
        doc = inspect.getdoc(target)

        if doc is None:
            # TODO: improve error handling
            return

        formatted_doc = doc_tool_parser(doc)

        parameters = []

        for param_name, param in inspect.signature(target).parameters.items():
            parameters.append(
                Parameter(
                    param_name,
                    param.annotation,
                    param.default,
                    formatted_doc["parameters"][param_name],
                )
            )

        return Tool(
            name,
            formatted_doc["description"],
            title=title,
            parameters=parameters,
            function=target,
        )

    if func is None:
        # uso como decorador con argumentos: @tool(title="...")
        return build
    return build(func)
