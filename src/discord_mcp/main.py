from discord_mcp.protocol_versions.mcp_2025_11_25 import Mcp20251125
from discord_mcp.protocol_versions.mcp_2026_07_28 import Mcp20260728
from discord_mcp.server import McpServer


def main():
    server = McpServer()
    server.add_implementation_protocol(Mcp20251125())
    server.add_implementation_protocol(Mcp20260728())
    server.run()


if __name__ == "__main__":
    main()
