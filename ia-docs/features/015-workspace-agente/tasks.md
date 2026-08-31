# 015 · Workspace de agente — Tareas

_Checklist accionable derivada del `plan.md`._

- [x] Modelo `app/models/feedback.py`: `Feedback` (suggestion_id único FK, tenant_id, action, reason, edited_content_hash, timestamps, índice compuesto).
- [x] `app/models/ai_suggestion.py`: ampliar `state` a `draft | accepted | edited | rejected | flagged`.
- [x] Schemas `app/schemas/ai.py`: `FeedbackIn`, `FeedbackOut`, `SuggestionOut`.
- [x] `app/services/feedback.py`: `FeedbackService.record()` (validación tenant, upsert, update de state, auditoría `ai.feedback`, métrica `ai_feedback_total`).
- [x] Rutas `app/api/routes_workspace.py`: `POST /v1/ai/tickets/{ticket_id}/feedback`, `GET /v1/ai/tickets/{ticket_id}/suggestions`, `GET /v1/workspace/my-tickets`.
- [x] Registrar router en `app/main.py`.
- [x] Tests `tests/test_workspace.py`: feedback por acción (accepted/edited/rejected/flagged), 404 otro tenant/sugerencia, 422 action, listado de sugerencias con aislamiento, bandeja solo mis tickets, auditoría y métricas.
- [x] Ejecutar suite completa sin regresión (`144 passed`).
- [x] Actualizar `ia_docs/cambios.md`, `roadmap.md` y spec/plan/tasks.
- [x] Feature 015 movida a "Hecho" en `ia_docs/constitution/roadmap.md`.

## Notas

- El agente genera sugerencias en 011-013; esta feature añade el "decidir sobre ellas" (CU-04/FR-09) y la bandeja de trabajo.
- Regenerar = rellamar `/suggested-reply`; escalar = `PATCH /v1/tickets/{id}` (ya existen).
- `SuggestionOut.output` se devuelve como se persistió (sin PII por diseño).
