# 006 · API core de tickets — Plan

_Cómo se implementa lo descrito en `spec.md`. Debe respetar la `constitution/`._

## Enfoque

Se agregan los modelos `Ticket` y `TicketMessage`, un repositorio tenant-scoped (reuso de `TenantScopedRepository`), y un router `/v1/tickets`. Toda escritura cifra los campos sensibles con `crypto` (feature 004) y audita con `AuditService` (feature 005). La autorización reusa el catálogo RBAC (feature 003).

## Estructura de archivos

```
app/
  models/
    ticket.py           # Ticket + TicketMessage (con campos cifrados como Text)
  schemas/
    ticket.py           # TicketCreate, TicketOut, MessageIn, TicketUpdate, ...
  repositories/
    tickets.py          # TicketRepository (filtro por tenant + decrypt al leer)
  api/
    routes_tickets.py   # /v1/tickets/*
tests/
  test_tickets.py       # CRUD, mensajes, cierre, cifrado, aislamiento, auditoría
```

## Implementación

1. `app/models/ticket.py`:
   - `Ticket`: id, tenant_id, subject (Text), description (Text, cifrado), category, priority, language, status, assignee_id, created_at, updated_at.
   - `TicketMessage`: id, ticket_id (FK), author_id, body (Text, cifrado), created_at.
   - `status` ∈ `open | in_progress | on_hold | closed`.
2. `app/schemas/ticket.py` — Pydantic v2: `TicketCreate`, `TicketUpdate`, `TicketOut` (descripción descifrada en la respuesta), `TicketMessageIn/Out`, listas paginadas.
3. `app/repositories/tickets.py` — `TicketRepository(TenantScopedRepository)`:
   - `create(...)` — cifra description con `settings.encryption_key`.
   - `get_or_none(...)` — descifra al devolver.
   - `list(status=, category=, priority=, assignee=, from/to)` — query con filtros y paginación.
   - `update(...)` / `close(...)`.
   - `add_message(...)` — cifra body.
4. `app/api/routes_tickets.py`:
   - `POST /v1/tickets` — `require_permissions(READ_TICKETS, EDIT_RESPONSE)` → crear; auditar `ticket.created`.
   - `GET /v1/tickets/{id}` — `require_permissions(READ_TICKETS)`; 404 si otro tenant.
   - `GET /v1/tickets` — filtros + `limit`/`offset`; auditar `ticket.list` (opcional, leve).
   - `PATCH /v1/tickets/{id}` — `require_permissions(EDIT_RESPONSE, SEND_RESPONSE)`.
   - `POST /v1/tickets/{id}/messages` — `require_permissions(EDIT_RESPONSE)`.
   - `POST /v1/tickets/{id}/close` — `require_permissions(SEND_RESPONSE)`; estado → closed.
5. Registrar router en `app/main.py`; importar modelos en `models/__init__.py`.
6. Tests en `tests/test_tickets.py`:
   - CRUD completo, validaciones (asunto/descripción obligatorios).
   - Mensajes y cierre.
   - Cifrado: description/mensaje no legibles en claro en DB; legibles vía API.
   - Aislamiento: tenant A no ve/edita ticket de tenant B (404).
   - Auditoría: eventos `ticket.created` etc. con trace_id.
   - Paginación y filtros.
7. Actualizar `ia_docs/cambios.md`, `roadmap.md`, spec/tasks.

## Decisiones

- **Cifrado de `description` y `body` de mensajes** — son los campos con PII (spec §9); se cifran con `crypto.encrypt_field`. Asunto también (puede contener datos), se decide cifrar `subject` igualmente.
- **Descifrado solo al leer** — la API devuelve texto plano al autorizado; la DB conserva ciphertext (cumple §10.5 "en reposo").
- **`GET /v1/tickets` devuelve descripción descifrada** — el agente autorizado la necesita; el cifrado es contra acceso no autorizado a la DB, no contra el usuario autenticado.
- **Filtros y paginación en el repositorio** — invariante ADR-001; los endpoints no construyen queries sueltas.
- **Permisos reutilizados** — se usa el catálogo existente; se evita inventar permisos nuevos sin OK.
- **Auditoría en escrituras** — created/update/message/close; las lecturas no se auditan (evita ruido) salvo caso concreto.

## Riesgos

- **Campos cifrados con queries de filtrado** — mitigación: no se filtra por campos cifrados (descripción); los filtros son por campos en claro (status, category, priority, assignee, fechas).
- **Descifrar en listado** — mitigación: se descifra por ticket; para MVP el volumen lo permite (optimización en feature 008).
- **Romper features previas** — mitigación: regresión de la suite completa.
- **Cierre sin permiso** — mitigación: `require_permissions(SEND_RESPONSE)` y test.
- **Mensajes huérfanos** — mitigación: FK con ondelete, y validación de tenant al agregar mensaje.