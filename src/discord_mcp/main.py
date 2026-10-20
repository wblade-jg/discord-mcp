import sys

from discord_mcp.bot import Bot
from discord_mcp.config import load_config
from discord_mcp.discord_api import DiscordApiClient
from discord_mcp.discord_tools import register_discord_tools
from discord_mcp.exceptions import ConfigError
from discord_mcp.protocol_versions.mcp_2025_11_25 import Mcp20251125
from discord_mcp.protocol_versions.mcp_2026_07_28 import Mcp20260728
from discord_mcp.server import McpServer

DISCORD_API_BASE_URL = "https://discord.com/api/v10"


def build_bot() -> Bot:
    config = load_config()
    client = DiscordApiClient(
        base_url=DISCORD_API_BASE_URL,
        headers={"Authorization": f"Bot {config.bot_token}"},
    )
    return Bot(discord_client=client)


def main():
    server = McpServer()
    server.add_implementation_protocol(Mcp20251125())
    server.add_implementation_protocol(Mcp20260728())

    try:
        bot = build_bot()
    except ConfigError as e:
        print(f"discord-mcp: {e}", file=sys.stderr)
        sys.exit(1)

    register_discord_tools(server, bot)
    server.run()


if __name__ == "__main__":
    main()
