---
inclusion: fileMatch
fileMatchPattern: '**/*.py'
---

# Convenciones de código (Python)

## Estilo y nombres
- Clases en PascalCase (`McpServer`, `JsonRpcRequest`); funciones y variables en snake_case; constantes en UPPER_CASE.
- Atributos "privados" con doble guion bajo (`__session_protocol` → name mangling); helpers de módulo con un guion bajo (`_find_key`).
- Indentación a 4 espacios, sin tabs. Pasa `uv run ruff check` y `uv run ruff format` antes de commitear.

## Docstrings y comentarios
- Docstrings y comentarios en español (igual que el resto del proyecto). Identificadores y mensajes de excepción en inglés.
- Docstrings estilo Google. Para herramientas (`@tool`), la primera línea es la descripción y la sección `Args:` con `nombre: descripción` por parámetro es obligatoria (la parsea `doc_tool_parser`).

## Tipos
- Usa type hints. Sintaxis 3.10+ permitida: `str | int`, `list[X]`, `match/case`.
- Callables: `collections.abc.Callable`. `Any` desde `typing`.

## Modelos
- Toda estructura de datos que se serialice a JSON va en `models/` como `pydantic.BaseModel` (v2). No uses `dataclass` para datos serializables.

## Excepciones
- Excepciones propias en `exceptions.py`, heredando de `Exception` y guardando su mensaje. Reutiliza las existentes antes de crear nuevas.

## Tests
- `tests/` con pytest. Sin red: usa fakes (`FakeResponse`, `ScriptedClient`, `FakeProtocol`) y `monkeypatch` para `time`/`random`.
- Un test por comportamiento, nombres descriptivos en inglés (`test_retry_on_503_then_success`).
- Cubre los reintentos/backoff del cliente y la resolución de protocolo del router.

## Seguridad
- No loguees el `TOKEN` ni datos sensibles. Valida/escapa los path params que vayan a URLs de la API de Discord si provienen de entrada del usuario.
