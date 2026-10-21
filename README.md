<div align="center">
  <img src="docs/images/logo.png" alt="discord-mcp" width="380">

  # discord-mcp

  *Servidor MCP para Discord, construido desde cero sobre JSON-RPC 2.0 por stdio.*

  [![CI](https://img.shields.io/github/actions/workflow/status/wblade-jg/discord-mcp/ci.yml?style=flat-square&label=CI)](https://github.com/wblade-jg/discord-mcp/actions/workflows/ci.yml)
  [![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/downloads/)
  [![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)

  [Características](#características) · [Herramientas](#herramientas) · [Inicio rápido](#inicio-rápido) · [Uso](#uso) · [Arquitectura](#arquitectura) · [Desarrollo](#desarrollo)
</div>

`discord-mcp` expone tu servidor de Discord a cualquier [cliente MCP](https://modelcontextprotocol.io): el agente puede listar los servidores (guilds) a los que pertenece el bot, ver sus canales de texto y leer los mensajes recientes. El bucle stdio, la negociación de protocolo y las herramientas están implementados desde cero: una línea JSON por mensaje, respuesta con `flush=True` y validación de esquemas con pydantic.

## Características

- **Tres herramientas listas para usar**: `get_servers`, `get_channels` y `get_messages`.
- **Caché con TTL**: servidores y canales se descargan una sola vez por sesión; los mensajes se revalidan por TTL y se sirven obsoletos si Discord falla al re-obtenerlos.
- **Llamadas resilientes**: reintentos con backoff exponencial, respeto del header `Retry-After` (HTTP 429) y mensajes claros ante errores comunes (401, 5xx, timeout).
- **Dos versiones de protocolo**: `2025-11-25` y `2026-07-28`, negociadas durante el primer `initialize`.
- **Errores JSON-RPC correctos**: `-32600` para peticiones inválidas y `-32602` para parámetros o versión de protocolo no soportados.

## Herramientas

| Herramienta | Parámetros | Devuelve |
| --- | --- | --- |
| `get_servers` | — | `name: <guild>, id: <id>` por cada servidor |
| `get_channels` | `server_name` | `name: <canal>, id: <id>` por cada canal de texto |
| `get_messages` | `server_name`, `channel_name` | Contenido de los mensajes recientes del canal |

> [!TIP]
> El orden esperado es `get_servers` → `get_channels` → `get_messages`: el `Bot` resuelve `name → id` a partir de su caché, así que los nombres deben coincidir exactamente con los de Discord. Los canales que no son de texto (type `0`) quedan filtrados de la caché.

## Inicio rápido

### Requisitos

- Python 3.10+ y [uv](https://docs.astral.sh/uv/)
- Un bot de Discord con token: créalo en el [portal de desarrolladores de Discord](https://discord.com/developers/applications) (pestaña **Bot** → **Reset Token**) e invítalo a tu servidor con permisos de lectura (`View Channel`, `Read Message History`).

### Instalación

```sh
git clone https://github.com/wblade-jg/discord-mcp.git
cd discord-mcp
uv sync --locked --all-extras --dev
cp .env.example .env
```

Pega tu token en `.env`:

```sh
TOKEN=tu-token-de-bot
```

> [!WARNING]
> `.env` está en `.gitignore`. Nunca lo subas a git ni imprimas el token en logs o salidas.

También puedes exportar `TOKEN` en el entorno en lugar de usar `.env`. Si no está configurada, el servidor imprime el error por stderr y sale con código `1`.

## Uso

### Conectar desde un cliente MCP

Configuración recomendada: el servidor lee el token del `.env` del repositorio, así el token no queda en el archivo de configuración del cliente.
 
```json
{
  "mcpServers": {
    "discord": {
      "command": "/ruta/absoluta/discord-mcp/.venv/bin/discord-mcp"
    }
  }
}
```

 
Alternativa con `uv`, pasando el token por `env`:


```json
{
  "mcpServers": {
    "discord": {
      "command": "uv",
      "args": ["run", "--directory", "/ruta/absoluta/discord-mcp", "discord-mcp"],
      "env": { "TOKEN": "tu-token-de-bot" }
    }
  }
}
```

> [!TIP]
> Tras `uv sync`, también puedes apuntar `command` a `.venv/bin/discord-mcp` directamente: sin `TOKEN` en el entorno, el servidor lee el `.env` del repositorio.

### Prueba manual por stdin

El servidor habla JSON-RPC 2.0 por stdio, así que puedes probarlo sin ningún cliente:

```sh
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25"}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
  | uv run discord-mcp
```

```jsonc
{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-11-25","capabilities":{"tools":{}},"serverInfo":{"name":"discord-mcp","version":"0.1.0"}}}
{"jsonrpc":"2.0","id":2,"result":{"tools":[{"name":"get_servers", ...}, ...]}}
```

### Versiones de protocolo

| Versión | Métodos soportados |
| --- | --- |
| `2025-11-25` | `initialize`, `tools/list`, `tools/call` |
| `2026-07-28` | `server/discover`, `tools/list`, `tools/call` (con `resultType: complete`) |

La versión se fija en la primera petición de la sesión que incluye `protocolVersion`; si falta o no está soportada, la respuesta es un error `-32602` con las versiones disponibles en `data`.

## Arquitectura

Flujo de una solicitud:

1. `main()` construye el `McpServer`, registra las dos versiones de protocolo, el `Bot` (con su `DiscordApiClient`) y las herramientas, y arranca el bucle stdio.
2. `McpServer.run()` lee stdin línea a línea, parsea JSON y delega en `handle()`. Un JSON inválido responde `-32600` sin matar el servidor.
3. `handle()` valida la petición con pydantic y resuelve la implementación de protocolo de la sesión.
4. El router de esa versión hace `match` sobre el método (`initialize`/`server/discover`, `tools/list`, `tools/call`); los errores de herramienta se capturan dentro del router.

Componentes:

| Módulo | Responsabilidad |
| --- | --- |
| `server.py` | `McpServer`: protocolos, capacidades y bucle de stdio |
| `tools.py` | Decorador `@tool` y esquema JSON generado desde la signatura y el docstring |
| `discord_tools.py` | Registro de las tres herramientas de Discord |
| `bot.py` | Caché en memoria de servidores, canales y mensajes (reloj inyectable) |
| `discord_api.py` | Cliente de la API de Discord + wrapper con reintentos y rate-limit |
| `protocol_versions/` | Una clase por versión de MCP con su `router()` |
| `models/` | Modelos pydantic de JSON-RPC y de dominio de Discord |

### Comportamiento de la caché

- **Servidores y canales**: se obtienen una única vez por sesión; `[]` cuenta como poblado y no se vuelve a llamar a la API.
- **Mensajes**: TTL en segundos (5 por defecto). Mientras `now - fetched_at < ttl` se sirve de caché; al expirar se re-obtiene, y si la re-obtención falla se sirve la caché obsoleta como *fallback*.
- **Fallos**: un error en la primera obtención se propaga; un fallo nunca deja datos parciales en la caché.

## Desarrollo

```sh
uv sync --locked --all-extras --dev   # dependencias
uv run pytest tests                   # tests (unitarios + property-based con hypothesis)
uv run ruff check                     # lint
uv run ruff format                    # formateo
uv lock                               # tras cambiar dependencias
```

En CI se ejecutan `ruff check`, `ruff format --check`, `uv lock --check` y `pytest` en cada PR hacia `main`.

## Recursos

- [Model Context Protocol](https://modelcontextprotocol.io) — especificación y documentación
- [Discord API documentation](https://discord.com/developers/docs/introduction) — endpoints y permisos del bot
