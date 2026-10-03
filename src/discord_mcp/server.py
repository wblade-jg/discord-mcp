import json
import sys
from typing import Any

from pydantic import ValidationError

from discord_mcp.exceptions import (
    MissingProtocolVersionError,
    NotSupportedProtocolError,
)
from discord_mcp.models.json_rpc import JsonRpcError, JsonRpcRequest
from discord_mcp.tools import Tool


class McpServer:
    def __init__(self):
        self.name = "discord-mcp"
        self.version = "0.1.0"
        self.__mcp_protocol_implementations = {}
        self.capabilities = {}
        self.__session_protocol = None
    
    def get_session_protocol(self, request) -> Any:
        """
        Returns:
            Un objeto que implementa el protocolo de la sesion
        Raises:
            NotSupportedProtocolError: Si el campo protocolVersion especifica una version que servidor no implementa
            MissingProtocolVersionError: Si dentro del objeto request no se incluye una clave '*protocolVersion'
        """
        if self.__session_protocol is None:
            self.establish_session_protocol(request) 
        return self.__session_protocol

    def establish_session_protocol(self, request):
        """
        Raises:
            NotSupportedProtocolError: Si el campo protocolVersion especifica una version que servidor no implementa
            MissingProtocolVersionError: Si dentro del objeto request no se incluye una clave '*protocolVersion'
        """
        protocol_version = _find_key(request.params, "protocolVersion")
        if protocol_version is None:
            raise MissingProtocolVersionError("Missing protocol version in request")

        if protocol_version not in self.get_supported_protocols():
            raise NotSupportedProtocolError(f"Protocol version {protocol_version} is not supported")
        self.__session_protocol = self.__mcp_protocol_implementations[protocol_version]

    def get_tools(self):
        return self.capabilities.setdefault("tools", [])

    def get_supported_protocols(self):
        return list(self.__mcp_protocol_implementations.keys())   

    def add_implementation_protocol(self, protocol_implementation):
        self.__mcp_protocol_implementations[protocol_implementation.protocol_version] = protocol_implementation

    def add_tool(self, tool: Tool):
        self.capabilities.setdefault("tools", []).append(tool)
    
    def add_resource(self, resource):
        self.capabilities.setdefault("resources", []).append(resource)
    
    def add_prompt(self, prompt):
        self.capabilities.setdefault("prompts", []).append(prompt)

    def run(self):
        for line in sys.stdin:
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                print(JsonRpcError.error_from_code(-32600).model_dump_json(), flush=True)
                continue

            try: 
                print(self.handle(data), flush=True)

            except NotSupportedProtocolError:
                print(JsonRpcError.error_from_code(-32602, id=data["id"]).add_error_data({
                                      "message": "Unavailable protocol",
                                      "supportedVersions": self.get_supported_protocols()}).model_dump_json(), flush=True)

            except MissingProtocolVersionError:
                print(JsonRpcError.error_from_code(-32602, id=data["id"]).add_error_data({
                    "message": "Missing protocol version in request"}).model_dump_json(), flush=True)

            except ValidationError:
                if "id" not in data:
                    print(JsonRpcError.error_from_code(-32602).model_dump_json(), flush=True)
            
                print(JsonRpcError.error_from_code(-32602, id=data["id"]).model_dump_json(), flush=True)

    def handle(self, data: dict):
        """
        Raises:
            NotSupportedProtocolError: Si el campo protocolVersion especifica una version que servidor no implementa
            MissingProtocolVersionError: Si dentro del objeto request no se incluye una clave '*protocolVersion'
            ValidationError: Si no se pasa un diccionario con la estructura que demanda el tipo JsonRpcRequest
        """
        request = JsonRpcRequest(**data)

        session_protocol = self.get_session_protocol(request)
        response = session_protocol.router(request, self)

        return response


def _find_key(dict, k):
    for key, value in dict.items():
        if k in key:
            return value
        if isinstance(value, dict):
            return _find_key(value, k)

