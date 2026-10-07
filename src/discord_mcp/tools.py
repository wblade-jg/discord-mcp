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
        self.parameters = {parameter.name: parameter for parameter in (parameters or [])}
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
        except Exception as e:
            raise ToolExecutionError(str(e))


def doc_tool_parser(doc: str):
    info = {}
    info["description"] = ""
    info["parameters"] = {}

    lines = doc.splitlines()

    info["description"] = lines[0]

    args_position = None
    for line in lines:
        if line.startswith("Args:"):
            args_position = lines.index(line)
            break

    if args_position is not None:
        for line in lines[args_position + 1 :]:
            param_name, param_description = line.split(":")
            info["parameters"].update({param_name.strip(): param_description.strip()})

    return info


def tool(func):
    name = func.__name__
    doc = inspect.getdoc(func)

    if doc is None:
        # TODO: improve error handling
        return

    formatted_doc = doc_tool_parser(doc)

    description = formatted_doc["description"]
    parameters = []

    for param_name, param in inspect.signature(func).parameters.items():
        parameters.append(
            Parameter(
                param_name,
                param.annotation,
                param.default,
                formatted_doc["parameters"][param_name],
            )
        )

    tool = Tool(name, description, parameters=parameters, function=func)

    return tool
