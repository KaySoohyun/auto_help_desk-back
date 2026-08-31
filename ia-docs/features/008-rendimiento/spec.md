# 008 · Optimización de consultas y rendimiento

**Estado:** implementado (pendiente merge a develop)

## Qué hace

Optimización de las consultas críticas de la Fase 3 (épica 3.4 del plan de ejecución), manteniendo invariantes de aislamiento (ADR-001) y de cifrado (features 006/007). Se enfoca en los cuellos de botella actuales del CRUD de tickets:

- **Índices compuestos** que cubren el patrón de listado más común (`WHERE tenant_id = ? AND status/filtro ORDER BY created_at DESC LIMIT/OFFSET`), evitando que SQLAlchemy produzca escaneos de tabla.
- **Proyecciones ligeras (campos diferidos)**: `description` y `body` son campos cifrados `TEXT` pesados; al listar tickets se cargan solo cuando se piden (détalle/mensajes) y no en listados.
- **Paginación eficiente y límites duros**: `LIMIT/OFFSET` con máximo impuesto por el API, `COUNT` optimizado, y se documenta keyset-pagination como mejora futura (backlog) para páginas profundas.
- **Configuración sin código mágico**: los índices se declaran en los modelos (SQLAlchemy), no se crean a mano en la base.

## Por qué

Con tickets, mensajes y auditoría creciendo por tenant, los listados con filtros y orden por `created_at` degradan rápido: hoy los índices son por columna sencilla (`status`, `tenant_id`, etc.), pero un query con filtro + ORDER + LIMIT necesita un índice compuesto alineado (spec §16, D-05 de arquitectura). Es el costo directo de la épica 3.4 del programa de ejecución.

## Criterios de aceptación

- [x] Índices compuestos en `tickets`: `(tenant_id, status)`, `(tenant_id, created_at)`, `(tenant_id, priority)`; en `messages`: `(ticket_id, created_at)`; en `audit_events`: `(tenant_id, created_at)`.
- [x] `description` de `Ticket` y `body` de `TicketMessage` son campos diferidos (deferred): no se cargan en listados; se cargan en obtener ticket/mensajes.
- [x] `GET /v1/tickets` con filtros no descarga los contenidos pesados de cada ticket (schema resumido sin `description`).
- [x] `GET /v1/tickets/{id}` y mensajes siguen devolviendo `description`/`body` (sin regresión).
- [x] Límites y defaults de `limit` documentados y aplicados (`limit` 1-200, offset ≥0).
- [x] Suite completa sin regresión (**76 tests**, incluye 8 nuevos de schema/rendimiento).
- [x] Prueba de que los índices existen en la metadata de los modelos (test de schema).

## Fuera de alcance

- **Caché con Redis / catálogos en caché** (D-09): se documenta como backlog; no se agrega la dependencia en este MVP para no inflar el stack.
- Vistas materializadas y particionamiento (dependen de PostgreSQL/RLS real, fuera del MVP SQLite).
- Keyset-pagination como API pública (se deja como recomendación documentada; la API actual mantiene page/offset).
- Observabilidad/métricas (feature 009).
- Cambios de esquema ya migrados: la base se recrea con `create_all` en pruebas; no hay esquema de migraciones formal aún.