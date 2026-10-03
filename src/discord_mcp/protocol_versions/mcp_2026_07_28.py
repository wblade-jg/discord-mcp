from discord_mcp.models.json_rpc import JsonRpcResponse


class Mcp20260728:
    def __init__(self):
        self.protocol_version = "2026-07-28"

    def router(self, request, mcp_server):
        match request.method:
            case "server/discover":
                return JsonRpcResponse(
                    id=request.id, 
                    result={"resultType": "complete", 
                            "supportedVersions": mcp_server.protocol_supported_versions, 
                            "capabilities": mcp_server.capabilities,
                            "_meta": {
                                "io.modelcontextprotocol/serverInfo": {
                                    "name": mcp_server.name, 
                                    "version": mcp_server.version
                                    }
                                }
                            })

            case "tools/list":
                return JsonRpcResponse(
                    id=request.id, 
                    result={
                        "resultType": "complete",
                        "tools": [
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
                        for tool in mcp_server.get_tools()]
                    })
