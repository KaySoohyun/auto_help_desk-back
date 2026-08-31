# 006 · API core de tickets — Tareas

_Checklist accionable derivada del `plan.md`. Tareas pequeñas y concretas; marca `[x]` al completarlas._

- [x] Crear modelos `Ticket` y `TicketMessage` (campos cifrados).
- [x] Crear schemas Pydantic v2 de tickets.
- [x] Crear `TicketRepository` (filtro tenant + cifrado al escribir + descifrado al leer).
- [x] Crear router `/v1/tickets` (create, get, list, update, messages, close).
- [x] Registrar router y modelos en `app/main.py` y `models/__init__.py`.
- [x] Escribir tests de CRUD, mensajes y cierre.
- [x] Escribir tests de cifrado en reposo y aislamiento multi-tenant.
- [x] Verificar regresión de la suite completa (**53 tests**, 14 nuevos).
- [x] Validar contra los criterios de aceptación de `spec.md`.
- [x] Actualizar `ia_docs/cambios.md`, `roadmap.md`, `tasks.md` y `spec.md`.
- [x] Ejecutar la suite completa y reportar resultados.

## Notas de implementación

- El repo devuelve `TicketView`/`MessageView` (dataclass espejo): descifra `subject`/`description`/`body` sin mutar el ORM, evitando persistir texto plano en commits posteriores.
- `PermissionError` de `_assert_tenant` (otro tenant) se convierte en 404 en el router, no en el repositorio (aislado de HTTP).
- `AuditEvent` no tiene `model_id`; el id del ticket se audita en `detail.ticket_id`.