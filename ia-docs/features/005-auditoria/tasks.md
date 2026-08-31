# 005 · Auditoría, logging y trazabilidad — Tareas

_Checklist accionable derivada del `plan.md`. Tareas pequeñas y concretas; marca `[x]` al completarlas._

- [x] Crear modelo `AuditEvent` (append-only, campos §11.2).
- [x] Crear `AuditService` con `log(...)` (solo insert, UTC).
- [x] Registrar eventos en auth: login ok/fallido, logout, refresh, register.
- [x] Crear dependencia/helper `get_trace_id` por request.
- [x] Crear endpoint `GET /audit/events` protegido (VIEW_AUDIT), filtrado por tenant y paginado.
- [x] Escribir tests de auditoría (eventos, append-only, aislamiento, paginación, sin PII).
- [x] Verificar regresión de la suite completa (features 002-004).
- [x] Validar contra los criterios de aceptación de `spec.md`.
- [x] Actualizar `ia_docs/cambios.md`, `roadmap.md`, `tasks.md` y `spec.md`.
- [x] Ejecutar la suite completa y reportar resultados.