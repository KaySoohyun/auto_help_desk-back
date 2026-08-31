# 015 · Workspace de agente — Plan

_Cómo se implementa lo descrito en `spec.md`._

## Enfoque

Añadir la capa de "decisiones del agente" sobre las sugerencias IA que ya genera 011-013, más la bandeja de trabajo. Reutiliza `TicketRepository` (tenant scope, ADR-001), `AuditService` y `metrics`. No se toca el pipeline LLM.

## Implementación

1. **Modelo `app/models/feedback.py`**:
   - `Feedback`: `id` PK, `suggestion_id` FK→`ai_suggestions.id` (ondelete CASCADE, unique), `tenant_id` (String(64), index), `action` (String(20)), `reason` (Text nullable), `edited_content_hash` (String(128) nullable), `created_at`/`updated_at`.
   - Índice compuesto `(tenant_id, suggestion_id)`.

2. **`AISuggestion.state`**: ampliar el set en `app/models/ai_suggestion.py` (comentario) a `draft | accepted | edited | rejected | flagged`. No es migración: columna String ya lo permite.

3. **Schemas `app/schemas/ai.py`**:
   - `FeedbackIn`: `suggestion_id: int`, `action: Literal["accepted","edited","rejected","flagged"]`, `reason: str | None`, `edited_content_hash: str | None`.
   - `FeedbackOut`: `suggestion_id`, `action`, `reason`, `edited_content_hash`, `created_at`.
   - `SuggestionOut`: `id`, `type`, `state`, `confidence`, `model`, `prompt_version`, `output` (dict), `created_at`.

4. **`app/services/feedback.py`**:
   - `FeedbackService(db, tenant_id)`:
     - `record(suggestion_id, action, reason, edited_content_hash, user_id, trace_id) -> FeedbackOut`:
       1. Carga la sugerencia con `WHERE id=? AND tenant_id=?` (join a ticket para validar el ticketId del path si aplica) → `None` → `PermissionError`.
       2. Upsert `Feedback` (si existe por suggestion_id → actualizar action/reason/hash).
       3. Actualiza `AISuggestion.state` según action: accepted→`accepted`, edited→`edited`, rejected→`rejected`, flagged→`flagged`.
       4. Commit.
       5. Audita `ai.feedback` con detail `{ticket_id, suggestion_id, action}` (sin reason ni PII).
       6. Métrica `ai_feedback_total{action}`.
   - La validación de que el ticket pertenece al tenant se hace consultando la sugerencia por su id y tenant; el ticket se valida antes en la ruta con `TicketRepository`.

5. **Rutas `app/api/routes_workspace.py`** (APIRouter):
   - `POST /v1/ai/tickets/{ticket_id}/feedback` (`EDIT_RESPONSE`): valida ticket del tenant (404 si no), luego `FeedbackService.record` (404 si sugerencia de otro tenant/no existe). 422 es gestionado por Pydantic (Literal).
   - `GET /v1/ai/tickets/{ticket_id}/suggestions` (`READ_TICKETS`): query de `AISuggestion` por tenant+ticket, ordenado por `created_at desc`.
   - `GET /v1/workspace/my-tickets` (`READ_TICKETS`): `TicketRepository.list(assignee_id=current_user.id, status in open|in_progress)` → `TicketListOut`.
   - Registrar en `app/main.py`.

6. **Tests `tests/test_workspace.py`**:
   - `_create_ticket`, `_classify`/`_summarize` helpers (como 011-013) para generar una sugerencia.
   - Casos: feedback accepted→state accepted; edited→edited; rejected→rejected; flagged→flagged; feedback otro tenant → 404; sugerencia inexistente → 404; action inválido → 422; `GET suggestions` devuelve solo las del tenant; `GET my-tickets` devuelve solo los asignados al agente; auditoría `ai.feedback` + métrica `ai_feedback_total`.

## Riesgos

- **Sugerencia de otro tenant**: se consulta `AISuggestion` por `id` + `tenant_id`; nunca se expone la de otro tenant (404).
- **Upsert de feedback**: se usa `suggestion_id` único; si ya existe se actualiza, preservando trazabilidad del último estado.
- **PII en `output`**: se devuelve `SuggestionOut.output` tal como se persistió (ya sin PII por diseño de 011-013); no se añade texto de entrada.
- **Regenerar/escalar**: documentado, no se implementa duplicado (reutiliza `/suggested-reply` y `PATCH /v1/tickets`).
