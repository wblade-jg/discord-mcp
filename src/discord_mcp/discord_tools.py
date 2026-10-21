from discord_mcp.tools import tool


def register_discord_tools(server, bot):
    @tool(title="Discord: List Servers")
    def get_servers() -> str:
        """Lista los servidores (guilds) de Discord a los que pertenece este bot.

        Devuelve una entrada por servidor en el formato
        "name: <nombre>, id: <id>", con el nombre y el id que asignó Discord.
        """
        servers = bot.get_servers()
        return "\n".join(f"name: {s.name}, id: {s.id}" for s in servers)

    @tool(title="Discord: List Text Channels")
    def get_channels(server_name: str) -> str:
        """Lista los canales de texto de un servidor de Discord.

        Args:
            server_name: Nombre exacto del servidor (guild) en Discord
        """
        channels = bot.get_channels(server_name)
        return "\n".join(f"name: {c.name}, id: {c.id}" for c in channels)

    @tool(title="Discord: Get Channel Messages")
    def get_messages(server_name: str, channel_name: str) -> str:
        """Obtiene los mensajes recientes de un canal de texto de Discord.

        Args:
            server_name: Nombre exacto del servidor (guild) en Discord
            channel_name: Nombre exacto del canal de texto en Discord
        """
        bulk = bot.get_messages(server_name, channel_name)
        return "\n".join(m.content for m in (bulk.messages or []))

    for t in (get_servers, get_channels, get_messages):
        server.add_tool(t)
