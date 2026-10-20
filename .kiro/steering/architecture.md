# Arquitectura

El servidor habla JSON-RPC 2.0 sobre stdio: una línea JSON por mensaje, respuesta impresa con `flush=True`.

## Flujo de una solicitud
1. `main()` (main.py) construye un `McpServer`, registra las implementaciones de protocolo (`Mcp20251125`, `Mcp20260728`), construye el `Bot` (`build_bot()`), registra las herramientas Discord (`register_discord_tools`) y llama a `server.run()`.
2. `McpServer.run()` (server.py) lee stdin línea a línea, parsea JSON y llama a `handle(data)`. Los errores de parseo/protocolo/validación se capturan aquí y se mapean a errores JSON-RPC (`-32600` para JSON inválido, `-32602` para errores de protocolo y validación).
3. `handle()` valida con `JsonRpcRequest` (pydantic), resuelve la implementación de protocolo de la sesión (`get_session_protocol` → `establish_session_protocol`, que busca `protocolVersion` en `params` con `_find_key`) y delega a `protocol.router(request, mcp_server)`.
4. Cada `router` (en `protocol_versions/`) usa `match request.method` para despachar: `initialize`/`server/discover`, `tools/list`, `tools/call`. Los errores de herramienta (`ToolNotFoundError`, `ToolExecutionError`, `TypeError`) se capturan dentro del router.

## Módulos
- `server.py` — `McpServer`: protocolos, capacidades (tools/resources/prompts) y bucle de stdio.
- `tools.py` — `Tool`, `Parameter`, `ExecuteToolRequest`, decorador `@tool` y `doc_tool_parser` (construye el esquema JSON desde la signatura + el docstring).
- `protocol_versions/` — una clase por versión de MCP, cada una con `protocol_version` y `router(request, mcp_server)`.
- `models/json_rpc.py` — `JsonRpcRequest` / `JsonRpcResponse` / `JsonRpcError` (pydantic).
- `models/discord_bot.py` — modelos de dominio: `Message`, `MessageBulk`, `Channel`, `Server`.
- `bot.py` — clase `Bot`: caché en memoria de servidores/canales/mensajes (TTL para mensajes), con `DiscordApiClient` y reloj (`clock`) inyectados por constructor.
- `discord_tools.py` — `register_discord_tools(server, bot)`: define y registra las herramientas Discord (`get_servers`, `get_channels`, `get_messages`) como cierres sobre el `Bot`.
- `discord_api.py` — `DiscordApiClient` y `ResilientClientWrapper` (reintentos, backoff y rate-limit contra la REST de Discord).
- `exceptions.py` — excepciones propias. `config.py` — carga `TOKEN` desde el entorno.

## Añadir una herramienta (tool)
1. Define una función con anotaciones de tipo y un docstring estilo Google: la primera línea es la descripción, y la sección `Args:` lleva `nombre: descripción` por parámetro. `doc_tool_parser` depende de ese formato.
2. Aplícale el decorador `@tool` (en `tools.py`); construye el `Tool` introspectando signatura + docstring.
3. Regístrala en el servidor con `server.add_tool(mi_tool)`.
4. Mapeo de tipos Python → JSON schema: `str→string`, `int→integer`, `float→number`, `bool→boolean` (el resto cae a `string`). Un parámetro es `required` solo si no tiene default.

## Añadir una versión de protocolo
1. Crea `protocol_versions/mcp_YYYY_MM_DD.py` con una clase que exponga `protocol_version` y `router(request, mcp_server)`.
2. Regístrala en `main()` con `server.add_implementation_protocol(...)`.

## Cliente HTTP resiliente
`ResilientClientWrapper` reintenta con backoff exponencial + jitter, respeta la cabecera `Retry-After` en 429, reintenta 5xx y errores de conexión/timeout, falla rápido en 4xx (salvo 429) y lanza `RateLimitExceeded` cuando la espera supera `max_delay`.

## Concurrencia

El servidor MCP procesa una petición a la vez (bucle síncrono sobre stdin) y atiende a un único cliente a la vez: no hay acceso concurrente a `McpServer`, `Bot` ni a la caché. No se requieren mecanismos de sincronización en el código de dominio.
