# 023 · Búsqueda por categorías y tags

**Estado:** propuesta

## Qué hace

Agrega búsqueda por texto en las listas de tickets (portal del cliente y bandeja/agente): al escribir en el buscador, el backend filtra los tickets cuya **categoría** o **tags** contengan el término, y devuelve solo esos resultados con su paginado y `total` correctos.

## Por qué

Hoy la búsqueda del dashboard del cliente se hace **en el frontend** sobre los tickets de la página ya descargados (máx. 100) y no cubre tags. Buscar en el backend permite resultados completos, consistentes con los filtros y el paginado real, sin depender de cuántos tickets se bajaron. Los campos elegidos (categoría y tags) están **en claro** en la DB, así que se pueden filtrar con SQL de forma eficiente y sin comprometer la política de cifrado en reposo.

## Criterios de aceptación

- [ ] `GET /v1/me/tickets?q=<término>` devuelve solo tickets cuya categoría o algún tag contenga el término (cierre por caso), con paginado y `total` consistentes.
- [ ] Lo mismo aplica al listado del agente (`/v1/tickets`) y a la bandeja de trabajo (`/v1/workspace/my-tickets`).
- [ ] La búsqueda es insensible a mayúsculas/minúsculas y matchea subcadenas.
- [ ] Si `q` está vacío o ausente, el comportamiento es idéntico al actual (sin filtro de texto).
- [ ] El frontend del cliente usa la búsqueda del backend y quita el filtrado en cliente.
- [ ] Tests: cobertura de buscar por categoría, por tag, sin resultados y sin regresión en listados.
- [ ] `q`, `category`, `priority`, `status`, `limit` y `offset` coexistena en la misma consulta.

## Fuera de alcance

- Buscar por **asunto (subject) y descripción**: están **cifrados en reposo** (política PII, ADR sobre cifrado); no se pueden filtrar con SQL `LIKE`. Requeriría un índice de texto plano (cambio de esquema) o descifrado en memoria (no escala). Se difiere.
- Buscar por **email / usuario / nombre del cliente**: descartado por el usuario.
- Búsqueda full-text (ranking de relevancia, stemming, multi-idioma).
