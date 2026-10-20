# Discord MCP

Servidor MCP (Model Context Protocol) para Discord construido desde cero sobre stdio JSON-RPC. El paquete es `discord_mcp` (nombre del proyecto en `pyproject.toml`: `discord-mcp`).

## Stack
- Python 3.14 en desarrollo (`.python-version`); compatible con `>=3.10` (`requires-python`). Usa sintaxis 3.10+ (`match/case`, `str | int`).
- Gestor de paquetes y build: `uv` (build-backend `uv_build`, `uv.lock` versionado).
- Dependencias runtime: `mcp[cli]`, `pydantic` v2, `python-dotenv`, `requests`.
- Dependencias dev: `pytest`, `ruff`, `hypothesis`.
- Layout `src/`: código en `src/discord_mcp/`, tests en `tests/`.

## Comandos (uv)
- Sincronizar dependencias: `uv sync --locked --all-extras --dev`
- Tests: `uv run pytest tests`
- Lint: `uv run ruff check` · Formatear: `uv run ruff format`
- Actualizar lockfile tras cambiar dependencias: `uv lock` (y commitear `uv.lock`)
- Ejecutar el servidor: `uv run discord-mcp` (lee JSON-RPC línea a línea desde stdin)

El CI (`.github/workflows/ci.yml`) solo ejecuta `uv run pytest tests`; ruff no corre en CI, pásalo localmente antes de commitear.

## Configuración
- `TOKEN` (token del bot de Discord) se carga desde `.env` con `python-dotenv` (ver `.env.example`).
- `.env` está en `.gitignore`: nunca lo commitees ni imprimas el token en logs/salidas.

## Git
- Ramas de feature bajo `feature/**`; los PR van a `main`.
- Mantén `uv.lock` commiteado y sincronizado con `pyproject.toml`.
- No commitees secretos, `.env` ni artefactos (`__pycache__`, `.ruff_cache`, `.pytest_cache`).
