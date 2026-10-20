"""Fakes para tests del ``Bot`` sin red.

Expone:

* ``FakeDiscordClient`` — cliente que imita la interfaz de ``DiscordApiClient``
  usada por ``Bot`` (``get_servers`` / ``get_channels`` / ``get_messages``).
  Registra cada llamada (con los ids recibidos) y permite programar
  respuestas fijas (que se devuelven siempre) o colas de respuestas que se
  consumen en orden. Una respuesta puede ser una excepción (``DiscordApiError``
  o ``RateLimitExceeded``) que se lanza al invocar el método.
* ``MutableClock`` — reloj inyectable y mutable para controlar tanto
  ``fetched_at`` (que el ``Bot`` fija al obtener mensajes) como ``now`` (que el
  ``Bot`` usa en la comprobación de validez), permitiendo ejercitar la frontera
  del TTL (``<`` vs ``>=``, incluido ``now - fetched_at == ttl``).
"""

from datetime import datetime, timedelta, timezone

from discord_mcp.exceptions import DiscordApiError, RateLimitExceeded
from discord_mcp.models.discord_bot import Channel, MessageBulk, Server

# Una respuesta programada es un valor de retorno o una instancia de una
# excepción de la API de Discord que el fake lanza al invocar el método.
ApiError = DiscordApiError | RateLimitExceeded
ServersResponse = list[Server] | ApiError
ChannelsResponse = list[Channel] | ApiError
MessagesResponse = MessageBulk | ApiError


class FakeDiscordClient:
    """Sustituto de ``DiscordApiClient`` para tests.

    Estilo ``ScriptedClient`` / ``FakeResponse`` de ``tests/test_client.py``.

    Uso:

    * ``set_servers`` / ``set_channels`` / ``set_messages`` — fija la
      respuesta que se devuelve siempre (a menos que haya cola pendiente).
    * ``enqueue_servers`` / ``enqueue_channels`` / ``enqueue_messages`` —
      encola respuestas que se consumen en orden; útil para secuencias
      «éxito → fallo» en re-obtenciones.
    * ``calls`` — diccionario con las listas de llamadas registradas;
      ``len(fake.calls["get_messages"])`` cuenta cuántas veces se invocó.
    """

    def __init__(self) -> None:
        # Registros de llamadas: cada lista guarda los argumentos recibidos
        # (``None`` para ``get_servers``, que no recibe argumentos).
        self.calls: dict[str, list] = {
            "get_servers": [],
            "get_channels": [],
            "get_messages": [],
        }
        # Respuesta fija por defecto (se devuelve si la cola está vacía).
        self._servers_default: ServersResponse = []
        self._channels_default: ChannelsResponse = []
        self._messages_default: MessagesResponse = MessageBulk()
        # Colas de respuestas que se consumen en orden.
        self._servers_queue: list[ServersResponse] = []
        self._channels_queue: list[ChannelsResponse] = []
        self._messages_queue: list[MessagesResponse] = []

    # --- Programación de respuestas fijas ------------------------------

    def set_servers(self, servers: ServersResponse) -> None:
        """Fija la respuesta de ``get_servers`` (valor o excepción a lanzar)."""
        self._servers_default = servers

    def set_channels(self, channels: ChannelsResponse) -> None:
        """Fija la respuesta de ``get_channels`` (valor o excepción a lanzar)."""
        self._channels_default = channels

    def set_messages(self, messages: MessagesResponse) -> None:
        """Fija la respuesta de ``get_messages`` (valor o excepción a lanzar)."""
        self._messages_default = messages

    # --- Programación de colas de respuestas ---------------------------

    def enqueue_servers(self, *responses: ServersResponse) -> None:
        """Encola respuestas de ``get_servers`` que se consumen en orden."""
        self._servers_queue.extend(responses)

    def enqueue_channels(self, *responses: ChannelsResponse) -> None:
        """Encola respuestas de ``get_channels`` que se consumen en orden."""
        self._channels_queue.extend(responses)

    def enqueue_messages(self, *responses: MessagesResponse) -> None:
        """Encola respuestas de ``get_messages`` que se consumen en orden."""
        self._messages_queue.extend(responses)

    # --- Resolución interna --------------------------------------------

    @staticmethod
    def _next(queue: list, default):
        # Devuelve el primer elemento encolado (consumiéndolo) o el default.
        if queue:
            return queue.pop(0)
        return default

    # --- Interfaz que imita a DiscordApiClient -------------------------

    def get_servers(self) -> list[Server]:
        self.calls["get_servers"].append(None)
        response = self._next(self._servers_queue, self._servers_default)
        if isinstance(response, Exception):
            raise response
        return response

    def get_channels(self, server_id: str) -> list[Channel]:
        self.calls["get_channels"].append(server_id)
        response = self._next(self._channels_queue, self._channels_default)
        if isinstance(response, Exception):
            raise response
        return response

    def get_messages(self, channel_id: str) -> MessageBulk:
        self.calls["get_messages"].append(channel_id)
        response = self._next(self._messages_queue, self._messages_default)
        if isinstance(response, Exception):
            raise response
        return response


class MutableClock:
    """Reloj inyectable y mutable para controlar ``now`` y ``fetched_at``.

    El ``Bot`` recibe ``clock`` por constructor y la invoca (``self._clock()``)
    tanto para fijar ``fresh.fetched_at`` como para calcular la validez. Al
    pasar este reloj, los tests controlan ambos instantes: llaman a
    ``get_messages`` en ``T1`` (``fetched_at = T1``), avanzan el reloj a ``T2``
    con :meth:`advance` y vuelven a llamar (validez = ``T2 - T1`` vs ``ttl``).
    """

    def __init__(self, start: datetime | None = None) -> None:
        self._current = (
            start if start is not None else datetime(2024, 1, 1, tzinfo=timezone.utc)
        )

    def __call__(self) -> datetime:
        # El ``Bot`` invoca el reloj así: ``self._clock()``.
        return self._current

    def now(self) -> datetime:
        return self._current

    def advance(self, seconds: float) -> None:
        """Avanza el reloj ``seconds`` hacia el futuro."""
        self._current = self._current + timedelta(seconds=seconds)

    def set(self, moment: datetime) -> None:
        """Fija el reloj a un instante concreto."""
        self._current = moment
