import json
import sys

from pydantic import ValidationError

from discord_mcp.models import JsonRpcError, JsonRpcRequest, JsonRpcResponse


class McpServer:
    def __init__(self):
        self.name = "discord-mcp"
        self.version = "0.1.0"
        self.protocol_supported_versions = ["2026-07-28"]

    def run(self):
        for line in sys.stdin:
            data = json.loads(line)
            
            try: 
                request = JsonRpcRequest(**data)
                self.__handle_request(request) 
            
            except ValidationError:
                # TODO: improve error handling
                if "id" not in data:
                    print(JsonRpcError(
                        jsonrpc="2.0",
                        id=None,
                        error={
                            "code": -32700, 
                            "message": "Parse error"
                            }).model_dump_json(), flush=True
                    )
                    continue

                print(JsonRpcError(
                        jsonrpc="2.0", 
                        id=data["id"], 
                        error={
                            "code": -32600, 
                            "message": "Invalid Request"
                            }).model_dump_json(), flush=True
                )
        
    def __handle_request(self, request):
        match request.method:
            case "server/discover":
                print(JsonRpcResponse(
                    jsonrpc="2.0", 
                    id=request.id, 
                    result={"resultType": "complete", 
                            "supportedVersions": self.protocol_supported_versions, 
                            "capabilities": {"tools": {}},
                            "_meta": {
                                "io.modelcontextprotocol/serverInfo": {
                                    "name": self.name, 
                                    "version": self.version
                                    }
                                }
                            }).model_dump_json(), flush=True
                )

            case "tools/list":
                print(JsonRpcResponse(
                    jsonrpc="2.0", 
                    id=request.id, 
                    result={"tools": [
                        {
                            "name": "get_messages",
                            "title": "Obtener mensajes",
                            "description": "Obtener mensajes de un canal especifico dentro de un servidor de discord",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "server_name": {
                                        "type": "string",
                                        "description": "Nombre del servidor"
                                    },
                                    "channel_name": {
                                        "type": "string",
                                        "description": "Nombre del canal"
                                    }

                                },
                                "required": ["server_name", "channel_name"]
                            }
                        }
                    ]}).model_dump_json(), flush=True
                )
