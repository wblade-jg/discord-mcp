import inspect


class Tool:
    def __init__(self, name: str, description: str, parameters: dict, title=""):
        self.name = name
        self.title = title
        self.description = description
        self.parameters = parameters


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
        for line in lines[args_position + 1:]:
            param_name, param_description = line.split(":")
            info["parameters"].update({param_name.strip(): param_description.strip()})

    return info


def tool(func):
    name = func.__name__
    doc = inspect.getdoc(func)

    if doc is None:
        #TODO: improve error handling
        return

    formatted_doc = doc_tool_parser(doc)

    description = formatted_doc["description"]
    parameters = {}

    for param_name, param in inspect.signature(func).parameters.items():
        parameters.update({
            param_name: {
                "type": param.annotation,
                "default": param.default,
                "description": formatted_doc["parameters"][param_name]
            }
        })
    tool = Tool(name, description, parameters)

    return tool
