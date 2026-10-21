# AGENTS.md

## Proyecto

Servidor MCP (Model Context Protocol) para Discord, construido desde cero sobre stdio JSON-RPC 2.0 (una línea JSON por mensaje, respuesta con `flush=True`).

- Paquete: `discord_mcp` (proyecto `discord-mcp` en `pyproject.toml`).
- Python `>=3.10` (dev en 3.14, `.python-version`); usa sintaxis 3.10+ (`match/case`, `str | int`).
- Gestor de paquetes/build: `uv` (backend `uv_build`, `uv.lock` versionado).
- Dependencias: `mcp[cli]`, `pydantic` v2, `python-dotenv`, `requests`. Dev: `pytest`, `ruff`, `hypothesis`.
- Layout `src/`: código en `src/discord_mcp/`, tests en `tests/`.

## Comandos

```sh
uv sync --locked --all-extras --dev   # sincronizar dependencias
uv run pytest tests                   # tests
uv run ruff check                     # lint (solo local, antes de commitear)
uv run ruff format                    # formatear
uv lock                               # tras cambiar dependencias (commitear uv.lock)
uv run discord-mcp                    # ejecutar el servidor (lee stdin)
```

CI (`.github/workflows/ci.yml`) ejecuta `uv run ruff check`, `uv run ruff format --check`, `uv lock --check` y `uv run pytest tests`; en local basta con `uv run ruff check` y `uv run ruff format` antes de commitear.

## Arquitectura

Flujo de una solicitud:

1. `main()` construye `McpServer`, registra los protocolos (`Mcp20251125`, `Mcp20260728`), construye el `Bot` (`build_bot()`), registra las herramientas Discord y llama a `server.run()`. Si falta `TOKEN` (`ConfigError`), imprime el error a stderr y sale con código 1 antes de servir.
2. `McpServer.run()` (server.py) lee stdin línea a línea, parsea JSON y llama a `handle(data)`. Errores de parseo/protocolo/validación → JSON-RPC (`-32600` JSON inválido, `-32602` protocolo/validación).
3. `handle()` valida con `JsonRpcRequest` (pydantic), resuelve la implementación de protocolo de la sesión (`get_session_protocol` → `establish_session_protocol`, busca `protocolVersion` con `_find_key`) y delega en `protocol.router(request, mcp_server)`.
4. Cada router (protocol_versions/) hace `match request.method`: `initialize`/`server/discover`, `tools/list`, `tools/call`. Los errores de herramienta (`ToolNotFoundError`, `ToolExecutionError`, `TypeError`) se capturan dentro del router.

Módulos:

- `server.py` — `McpServer`: protocolos, capacidades (tools/resources/prompts), bucle de stdio.
- `tools.py` — `Tool`, `Parameter`, `ExecuteToolRequest`, decorador `@tool` (acepta `title=`), `doc_tool_parser` (esquema JSON desde signatura + docstring).
- `bot.py` — clase `Bot` (no pydantic): caché en memoria de servidores/canales/mensajes con reloj inyectado.
- `discord_tools.py` — `register_discord_tools(server, bot)`: tres cierres `@tool` (`get_servers`, `get_channels`, `get_messages`) que delegan en el `Bot`.
- `discord_api.py` — `DiscordApiClient` y `ResilientClientWrapper` (reintentos, backoff, rate-limit).
- `protocol_versions/` — una clase por versión de MCP, con `protocol_version` y `router(request, mcp_server)`.
- `models/json_rpc.py` — `JsonRpcRequest`/`JsonRpcResponse`/`JsonRpcError` (pydantic).
- `models/discord_bot.py` — modelos de dominio: `Message`, `MessageBulk` (`fetched_at`, `ttl` default 5), `Channel` (`type` default 0 = texto), `Server`.
- `exceptions.py` — excepciones propias. `config.py` — carga `TOKEN` desde el entorno (`python-dotenv`).

### Bot (caché)

- Se obtiene exclusivamente vía `DiscordApiClient` inyectado por constructor (+ `clock: Callable[[], datetime] = _utc_now`, UTC). No importa `requests`.
- Servidores y canales de un servidor: se obtienen **una única vez** por sesión; `[]` cuenta como poblado. Los canales se filtran a type 0 (texto) en el fetch: la caché solo almacena texto.
- Mensajes: TTL en segundos; válida mientras `now - fetched_at < ttl`; al expirar re-fetch; re-fetch fallido sirve la caché obsoleta como *fallback*; primera obtención fallida **propaga**.
- Asigna caché solo tras éxito (un fallo nunca deja datos parciales). Resuelve `name → id` desde la caché; si no coincide lanza `NotFoundError`.
- Orden esperado por las herramientas: `get_servers()` → `get_channels(server_name)` → `get_messages(server_name, channel_name)`.
- Concurrencia: el servidor procesa una petición a la vez (single-threaded, un cliente); no se requieren locks.

### Añadir una herramienta (tool)

1. Función con anotaciones de tipo y docstring estilo Google: el párrafo inicial (hasta `Args:`) = descripción; sección `Args:` con `nombre: descripción` por parámetro (la parsea `doc_tool_parser`).
2. Decorador `@tool` (tools.py); opcionalmente `@tool(title="...")` para el título visible en `tools/list`.
3. Registrar con `server.add_tool(mi_tool)` (o vía `register_discord_tools`).
4. Tipos Python → JSON schema: `str→string`, `int→integer`, `float→number`, `bool→boolean` (resto → `string`). Un parámetro es `required` solo si no tiene default.

### Añadir una versión de protocolo

1. Crear `protocol_versions/mcp_YYYY_MM_DD.py` con clase que exponga `protocol_version` y `router(request, mcp_server)`.
2. Registrar en `main()` con `server.add_implementation_protocol(...)`.

## Convenciones Python

- Clases PascalCase; funciones/variables snake_case; constantes UPPER_CASE. Atributos "privados" con `__` (name mangling); helpers de módulo con `_`.
- Indentación 4 espacios. `uv run ruff check` y `uv run ruff format` antes de commitear.
- Docstrings y comentarios **en español**; identificadores y mensajes de excepción **en inglés**. Docstrings estilo Google.
- Type hints siempre; sintaxis 3.10+ permitida (`str | int`, `list[X]`, `match/case`); callables desde `collections.abc.Callable`.
- Datos serializables a JSON → `models/` como `pydantic.BaseModel` v2. No usar `dataclass` para eso.
- Excepciones propias en `exceptions.py` heredando de `Exception`; reutilizar las existentes antes de crear nuevas.

## Seguridad

- `.env` está en `.gitignore`: no commitear ni imprimir `TOKEN` en logs/salidas.
- Validar/escapar los path params que vayan a URLs de la API de Discord si provienen de entrada del usuario.

## Git

- Ramas `feature/**, fix/**, docs/**`; PRs hacia `main`.
- Mantener `uv.lock` commiteado y sincronizado con `pyproject.toml`.
- No commitear secretos, `.env` ni artefactos (`__pycache__`, `.ruff_cache`, `.pytest_cache`).
