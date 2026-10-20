# Requirements Document

## Introduction

Este documento describe el comportamiento de caché que se agregará al componente `Bot` para obtener servidores, canales y mensajes de la API de Discord a través del `DiscordApiClient` y actuar como caché en memoria. Los servidores y los canales de un servidor se obtienen de la API una única vez y se sirven desde caché en las peticiones posteriores; los mensajes se cachean con un tiempo de invalidación (TTL, en segundos) y se vuelven a obtener de la API cuando dicho tiempo expira. La lógica de invalidación de mensajes aprovecha los campos existentes `fetched_at` y `ttl` del modelo `MessageBulk`.

El llamador (una herramienta del servidor MCP) identifica servidores y canales por su `name`. El `Bot` resuelve cada nombre a su `id` usando los servidores y canales cacheados y pasa el `id` al `DiscordApiClient`, que opera con identificadores. Un servidor o canal no encontrado se indica al llamador.

El `Bot` obtiene los datos exclusivamente a través del `DiscordApiClient`, inyectado por constructor, de modo que todo el tráfico HTTP se beneficia de los reintentos, el backoff y el control de rate-limit del `ResilientClientWrapper` y de modo que las pruebas puedan inyectar un fake sin red.

## Glossary

- **Bot**: Componente que actúa como caché en memoria de servidores, canales y mensajes y que obtiene los datos de Discord a través del `DiscordApiClient`. La forma exacta de la clase (pydantic o clase normal) y su ubicación de archivo se definen en la fase de diseño.
- **DiscordApiClient**: Cliente HTTP (`src/discord_mcp/discord_api.py`) que realiza las peticiones a la REST API de Discord y expone los métodos `get_servers`, `get_channels` y `get_messages`.
- **Servidor (Server)**: Un guild de Discord, identificado por `id` y `name`.
- **Canal (Channel)**: Un canal dentro de un servidor, identificado por `id` y `name`.
- **Mensaje (Message)**: Un mensaje publicado en un canal.
- **MessageBulk**: Estructura que agrupa los mensajes de un canal junto con `fetched_at` (momento en que se obtuvieron) y `ttl` (tiempo de vida de la caché, en segundos; por defecto 5).
- **Caché**: Almacenamiento en memoria, dentro del `Bot`, de los datos obtenidos de la API para evitar peticiones redundantes.
- **TTL (Time To Live)**: Tiempo de vida de los mensajes en caché, en segundos. Unos mensajes en caché se consideran válidos mientras el tiempo transcurrido desde `fetched_at` sea estrictamente menor que `ttl`, y expirados cuando es mayor o igual que `ttl`.
- **Invalidación**: Determinación de si los mensajes en caché siguen siendo válidos o deben volver a obtenerse de la API.
- **Identificación por nombre**: Mecanismo por el cual el llamador identifica servidores y canales mediante su `name` en lugar de su `id`.
- **Resolución de nombre a id**: Proceso por el cual el `Bot`, dado un `server_name` o `channel_name`, busca en la caché el servidor o canal correspondiente y obtiene su `id` para pasarlo al `DiscordApiClient`.
- **First-fetch (primera obtención)**: Primera vez que se solicitan los mensajes de un canal sin caché válida; en caso de fallo no existe caché obsoleta que servir y el error se propaga.
- **Re-fetch (re-obtención)**: Obtención de mensajes cuando la caché previa ha expirado; en caso de fallo se sirve la caché obsoleta como fallback.
- **Fallback de caché obsoleta**: Comportamiento por el cual, ante el fallo de una re-obtención de mensajes, el `Bot` devuelve los mensajes de la caché previa en lugar de propagar el error.
- **DiscordApiError**: Excepción propia (`exceptions.py`) para errores de la API de Discord.
- **RateLimitExceeded**: Excepción propia (`exceptions.py`) para cuando la espera impuesta por un rate-limit supera el máximo permitido.

## Requirements

### Requirement 1: Obtención y caché de servidores

**User Story:** Como servidor MCP, quiero que el `Bot` obtenga y cachee los servidores del bot, para que las peticiones posteriores no vuelvan a consultar la API de Discord.

#### Acceptance Criteria

1. WHEN se solicita la lista de servidores y la caché de servidores no ha sido poblada, THE Bot SHALL obtener los servidores mediante el DiscordApiClient y poblar la caché de servidores.
2. WHILE la caché de servidores ha sido poblada, THE Bot SHALL devolver los servidores desde la caché sin invocar al DiscordApiClient, tratando una lista vacía como estado poblado.
3. WHEN se solicita un servidor por `server_name` y no existe un servidor con ese nombre en la caché de servidores, THE Bot SHALL indicar al llamador que el servidor no fue encontrado.

### Requirement 2: Obtención y caché de canales por nombre de servidor

**User Story:** Como servidor MCP, quiero que el `Bot` obtenga y cachee los canales de un servidor identificado por nombre, para que las peticiones posteriores de canales de ese servidor no vuelvan a consultar la API.

#### Acceptance Criteria

1. WHEN se solicitan los canales de un servidor identificado por `server_name` y la caché de canales de ese servidor no ha sido poblada, THE Bot SHALL resolver el servidor a su `id` usando la caché de servidores, obtener los canales mediante el DiscordApiClient y poblar la caché de canales del servidor.
2. WHILE la caché de canales de un servidor ha sido poblada, THE Bot SHALL devolver los canales desde la caché sin invocar al DiscordApiClient, tratando una lista vacía como estado poblado.
3. WHEN se solicitan los canales de un servidor identificado por `server_name` y el servidor no se encuentra en la caché de servidores, THE Bot SHALL indicar al llamador que el servidor no fue encontrado.

### Requirement 3: Obtención de mensajes con invalidación por TTL

**User Story:** Como servidor MCP, quiero que el `Bot` obtenga los mensajes de un canal identificado por nombre y los cachee con un tiempo de invalidación, para que los mensajes se mantengan actualizados sin consultar la API en cada petición.

#### Acceptance Criteria

1. WHEN se solicitan los mensajes de un canal identificado por `server_name` y `channel_name` y no existe caché válida (los mensajes son `None` o `fetched_at` es `None`), THE Bot SHALL resolver el canal a su `id` usando la caché de canales del servidor, obtener los mensajes mediante el DiscordApiClient, registrar el momento de obtención en `fetched_at` y almacenar los mensajes en caché.
2. WHILE los mensajes en caché de un canal son válidos (el tiempo transcurrido desde `fetched_at`, en segundos, es estrictamente menor que `ttl`), THE Bot SHALL devolver los mensajes desde la caché sin invocar al DiscordApiClient.
3. WHEN los mensajes en caché de un canal han expirado (el tiempo transcurrido desde `fetched_at`, en segundos, es mayor o igual que `ttl`), THE Bot SHALL obtener los mensajes nuevamente mediante el DiscordApiClient, actualizar `fetched_at` y actualizar la caché.
4. WHEN la primera obtención de mensajes (sin caché válida previa) falla, THE Bot SHALL propagar el error al llamador, dado que no existe caché obsoleta para servir como fallback.
5. WHEN la re-obtención de mensajes expirados falla, THE Bot SHALL servir la caché obsoleta como fallback al llamador en lugar de propagar el error.
6. WHEN se solicitan los mensajes de un canal y el canal no se encuentra en la caché de canales del servidor, THE Bot SHALL indicar al llamador que el canal no fue encontrado.

### Requirement 4: Uso exclusivo del DiscordApiClient

**User Story:** Como desarrollador, quiero que el `Bot` obtenga los datos de Discord exclusivamente a través del `DiscordApiClient`, para que todas las peticiones HTTP se beneficien de los reintentos, el backoff y el control de rate-limit implementados en `ResilientClientWrapper`.

#### Acceptance Criteria

1. THE Bot SHALL obtener los servidores, canales y mensajes de la API de Discord exclusivamente a través del DiscordApiClient.
2. THE Bot SHALL NOT instanciar ni mantener un `requests.Session` ni invocar el paquete `requests` directamente; todo el tráfico HTTP se realiza a través de los métodos `get_servers`, `get_channels` y `get_messages` del DiscordApiClient.

### Requirement 5: Inyección del DiscordApiClient por constructor

**User Story:** Como desarrollador, quiero que el `Bot` reciba el `DiscordApiClient` por constructor, para que el componente sea testeable inyectando un fake sin red.

#### Acceptance Criteria

1. THE Bot SHALL recibir una instancia de DiscordApiClient mediante su constructor.
2. WHEN se inyecta un fake de DiscordApiClient en el constructor, THE Bot SHALL delegar las llamadas de obtención de servidores, canales y mensajes al fake inyectado en lugar de un cliente real.

### Requirement 6: Manejo de errores de la API de Discord

**User Story:** Como servidor MCP, quiero que el `Bot` maneje los errores de la API de Discord de forma consistente, para que las herramientas que lo consumen reciban errores claros y la caché no quede en un estado inconsistente.

#### Acceptance Criteria

1. WHEN el DiscordApiClient lanza DiscordApiError o RateLimitExceeded durante una primera obtención (sin caché válida) de servidores, canales o mensajes, THE Bot SHALL propagar la excepción al llamador.
2. WHEN el DiscordApiClient lanza DiscordApiError o RateLimitExceeded durante la re-obtención de mensajes expirados, THE Bot SHALL servir la caché obsoleta como fallback al llamador en lugar de propagar la excepción.
3. WHEN una operación de obtención falla, THE Bot SHALL conservar el estado previo de la caché sin modificarla con datos incompletos.

## Decisiones de diseño

- **Inyección del DiscordApiClient (vía constructor)** — Resuelto: el componente que cachea recibe el `DiscordApiClient` por constructor (inyección de dependencias) para permitir inyectar un fake en tests. Si es necesario, el `Bot` se reconstruye como una clase normal (sin pydantic) en un archivo separado e independiente de `models/`; la ubicación exacta del archivo queda para la fase de diseño.
- **Unidad del TTL** — Confirmado: segundos.
- **Identificación por nombre** — Resuelto: el llamador identifica servidores y canales por `name`; el `Bot` resuelve name→id usando los servidores y canales cacheados; un servidor o canal no encontrado se indica al llamador.
- **Fallback con caché obsoleta** — Resuelto: la re-obtención de mensajes expirados fallida sirve la caché obsoleta como fallback; la primera obtención fallida (sin caché) propaga el error, dado que no hay fallback posible.
- **Concurrencia** — Confirmado: el servidor atiende a un único cliente a la vez (single-threaded); no se requieren mecanismos de sincronización.

## Nota sobre concurrencia

El servidor MCP procesa stdin línea a línea de forma síncrona y atiende a un único cliente a la vez. Se asume acceso single-threaded al `Bot`; por tanto, no se requieren mecanismos de sincronización (bloqueos, mutex) para la caché. Esta suposición no es un requisito funcional y no se traduce en criterios de aceptación.
