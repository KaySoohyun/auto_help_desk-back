# 008 · Optimización de consultas y rendimiento — Tareas

_Checklist accionable derivada del `plan.md`._

- [x] Agregar índices compuestos en `Ticket` (tenant+status, tenant+created_at, tenant+priority).
- [x] Agregar índice compuesto en `TicketMessage` (ticket_id, created_at).
- [x] Agregar índice compuesto en `AuditEvent` (tenant_id, created_at).
- [x] Marcar `Ticket.description` y `TicketMessage.body` como columnas diferidas (deferred).
- [x] Crear `TicketSummaryView` y `TicketSummaryOut` para que el listado no toque la columna diferida (evita N+1).
- [x] Verificar que `GET /v1/tickets/{id}` y mensajes siguen devolviendo `description`/`body` (sin regresión).
- [x] Escribir test de schema: índices presentes en metadata (`tests/test_schema.py`).
- [x] Escribir test de que listar no dispara lazy-load por fila (cuenta SELECTs).
- [x] Verificar que los tests de cifrado en reposo (lectura directa de DB) siguen pasando.
- [x] Ejecutar la suite completa (`76 tests`) y reportar.
- [x] Actualizar `ia_docs/cambios.md`, `roadmap.md`, spec/tasks. Validar criterios de aceptación.

## Notas de implementación

- El listado de tickets ahora NO expone `description` (schema resumido `TicketSummaryOut`); el detalle y mensajes sí.
- El test de cifrado en reposo se ajustó para leer los valores dentro de la sesión (evita `DetachedInstanceError` por columna diferida).