from collections.abc import Callable
from datetime import datetime, timezone

from discord_mcp.discord_api import DiscordApiClient
from discord_mcp.exceptions import DiscordApiError, NotFoundError, RateLimitExceeded
from discord_mcp.models.discord_bot import Channel, MessageBulk, Server


def _utc_now() -> datetime:
    """Reloj por defecto del Bot: hora actual en UTC (consistente con MutableClock)."""
    return datetime.now(timezone.utc)


class Bot:
    """Caché en memoria de servidores, canales y mensajes de Discord.

    Obtiene los datos exclusivamente a través del DiscordApiClient inyectado
    por constructor. Los servidores y los canales de un servidor se obtienen
    una única vez por sesión; los mensajes se cachean con un TTL (en segundos)
    y se re-obtienen al expirar, sirviendo la caché obsoleta como fallback
    cuando la re-obtención falla. El llamador identifica servidores y canales
    por ``name``; el ``Bot`` resuelve ``name → id`` usando la caché y pasa el
    ``id`` al cliente.
    """

    def __init__(
        self,
        discord_client: DiscordApiClient,
        clock: Callable[[], datetime] = _utc_now,
    ):
        self._client = discord_client
        self._clock = clock
        # None  => caché de servidores no poblada.
        # []    => poblada (vacía). Se sirve desde caché sin llamar al cliente.
        self._servers: list[Server] | None = None

    def get_servers(self) -> list[Server]:
        if self._servers is None:
            # propaga en fallo (6.1); _servers solo se asigna tras éxito
            self._servers = self._client.get_servers()
        return self._servers

    def get_channels(self, server_name: str) -> list[Channel]:
        server = self._resolve_server(server_name)
        if server.channels is None:
            # propaga en fallo (6.1); server.channels solo se asigna tras éxito
            server.channels = self._client.get_channels(server.id)
        return server.channels

    def get_messages(self, server_name: str, channel_name: str) -> MessageBulk:
        server = self._resolve_server(server_name)
        channel = self._resolve_channel(server, channel_name)

        cached = channel.messages
        if self._is_valid(cached):
            return cached  # acierto de caché: no se invoca al cliente (3.2)

        has_stale = cached is not None and cached.fetched_at is not None
        try:
            fresh = self._client.get_messages(channel.id)
            fresh.fetched_at = self._clock()  # el Bot registra el momento (3.1)
            # solo tras éxito -> preserva el estado en fallo (6.3)
            channel.messages = fresh
            return fresh
        except (DiscordApiError, RateLimitExceeded):
            if has_stale:
                return cached  # re-fetch fallido: sirve la obsoleta (3.5/6.2)
            raise  # primera obtención fallida: propaga (3.4/6.1)

    def _resolve_server(self, server_name: str) -> Server:
        if self._servers is None:
            raise NotFoundError("server", server_name)
        for server in self._servers:
            if server.name == server_name:
                return server
        raise NotFoundError("server", server_name)

    def _resolve_channel(self, server: Server, channel_name: str) -> Channel:
        if server.channels is None:
            raise NotFoundError("channel", channel_name)
        for channel in server.channels:
            if channel.name == channel_name:
                return channel
        raise NotFoundError("channel", channel_name)

    def _is_valid(self, bulk: MessageBulk | None) -> bool:
        if bulk is None or bulk.fetched_at is None:
            return False
        elapsed = (self._clock() - bulk.fetched_at).total_seconds()
        return elapsed < bulk.ttl
