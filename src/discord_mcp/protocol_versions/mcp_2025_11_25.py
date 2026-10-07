from discord_mcp.exceptions import ToolExecutionError, ToolNotFoundError
from discord_mcp.models.json_rpc import JsonRpcError, JsonRpcResponse
from discord_mcp.tools import ExecuteToolRequest


class Mcp20251125:
    def __init__(self):
        self.protocol_version = "2025-11-25"

    def router(self, request, mcp_server):
        match request.method:
            case "initialize":
                return JsonRpcResponse(
                    id=request.id,
                    result={
                        "protocolVersion": self.protocol_version,
                        "capabilities": mcp_server.get_capabilities(),
                        "serverInfo": {
                            "name": mcp_server.name,
                            "version": mcp_server.version,
                        },
                    },
                ).model_dump_json()

            case "tools/list":
                return JsonRpcResponse(
                    id=request.id,
                    result={
                        "tools": [
                            tool.to_dict()
                            for tool in mcp_server.get_tools().values()
                        ]
                    },
                ).model_dump_json()

            case "tools/call":
                tool_info = ExecuteToolRequest(**request.params)
                try:
                    execution_result = mcp_server.execute_tool(tool_info)
                    return JsonRpcResponse(
                        id=request.id,
                        result={
                            "content": [{"type": "text", "text": execution_result}],
                        },
                    ).model_dump_json()

                except ToolNotFoundError as e:
                    return JsonRpcError.error_from_code(
                        -32602, id=request.id
                    ).add_error_data({"Unknown tool": e.tool_name}).model_dump_json()

                except ToolExecutionError as e:
                    return JsonRpcResponse(
                        id=request.id,
                        result={
                            "content": [{"type": "text", "text": e.message}],
                            "isError": True,
                        },
                    ).model_dump_json()

                except TypeError as e:
                    return JsonRpcError.error_from_code(
                        -32602, id=request.id
                    ).add_error_data({"message": str(e)}).model_dump_json()
