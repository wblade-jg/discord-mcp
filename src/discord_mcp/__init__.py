from discord_mcp.discord_api import DiscordApiClient
from discord_mcp.config import load_config
from discord_mcp.models import Bot, Channel, MessageBulk, Server

__all__ = [
    "Bot",
    "Channel",
    "DiscordApiClient",
    "MessageBulk",
    "Server",
    "load_config",
    "main",
]


def main():
    config = load_config()

    headers = {"Authorization": f"Bot {config.bot_token}", "User-Agent": "MyBot/1.0"}
    client_api = DiscordApiClient("https://discord.com/api/v10", headers)

    bot = Bot(token=config.bot_token)
    bot.servers = client_api.get_servers()

    print(bot.servers)

    server = bot.get_server_by_name("El servidor de Windbladejg7")

    if server is not None:
        server.channels = client_api.get_channels(server.id)
        print(server.channels)


if __name__ == "__main__":
    main()
