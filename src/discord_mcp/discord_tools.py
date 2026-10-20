from discord_mcp.tools import tool


def register_discord_tools(server, bot):
    @tool
    def get_servers() -> str:
        """Lista los servidores (guilds) a los que pertenece el bot."""
        servers = bot.get_servers()
        return ", ".join(f"{s.name} ({s.id})" for s in servers)

    @tool
    def get_channels(server_name: str) -> str:
        """Lista los canales de un servidor.

        Args:
            server_name: Nombre del servidor (guild).
        """
        channels = bot.get_channels(server_name)
        return ", ".join(f"{c.name} ({c.id})" for c in channels)

    @tool
    def get_messages(server_name: str, channel_name: str) -> str:
        """Obtiene los mensajes recientes de un canal.

        Args:
            server_name: Nombre del servidor (guild).
            channel_name: Nombre del canal.
        """
        bulk = bot.get_messages(server_name, channel_name)
        return "\n".join(m.content for m in (bulk.messages or []))

    for t in (get_servers, get_channels, get_messages):
        server.add_tool(t)
