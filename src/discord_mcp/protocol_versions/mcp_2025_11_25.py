from discord_mcp.models.json_rpc import JsonRpcResponse


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
                        "capabilities": mcp_server.capabilities,
                        "serverInfo": {
                            "name": mcp_server.name, 
                            "version": mcp_server.version
                        }
                    }).model_dump_json()

            case "tools/list":
                return JsonRpcResponse(
                    id=request.id, 
                    result={"tools": [
                        {
                            "name": tool.name,
                            "title": tool.title,
                            "description": tool.description,
                            "inputSchema": {
                                "type": "object",
                                "properties": tool.parameters,
                                "required": ["server_name", "channel_name"]
                            }
                        }
                    for tool in mcp_server.get_tools()]})
