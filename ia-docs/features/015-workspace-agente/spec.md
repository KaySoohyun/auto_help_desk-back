# 015 · Workspace de agente

**Estado:** implementado

## Qué hace

Backend del workspace de agente (Fase 5, épicas 5.1-5.3; sin UI en el MVP): la parte que el panel de asistencia IA consume para aceptar/editar/rechazar sugerencias y ver su cola de trabajo. Es la primera feature de Fase 5 y cierra el ciclo del agente sobre las sugerencias generadas en 011-013.

- **Feedback del agente (CU-04, FR-05, spec §15.4)**: `POST /v1/ai/tickets/{ticketId}/feedback` registra la decisión del agente sobre una sugerencia (`accepted | edited | rejected | flagged`), actualiza el estado de la `AISuggestion` (FR-09: trazabilidad del estado final) y queda auditado.
- **Panel IA por ticket (spec §13.2)**: `GET /v1/ai/tickets/{ticketId}/suggestions` lista las sugerencias de IA del ticket (clasificación, resumen, respuesta) con su estado, para que el panel las muestre.
- **Bandeja de trabajo del agente (épica 5.2)**: `GET /v1/workspace/my-tickets` devuelve los tickets asignados al agente autenticado (cola propia), abiertos o en progreso.
- **Regenerar / escalar**: reutiliza endpoints existentes (volver a llamar a `/suggested-reply` regenera; `PATCH /v1/tickets/{id}` permite reasignar/cambiar prioridad para escalar). No se duplican.

## Por qué

CU-04 exige que el agente pueda aceptar, editar, rechazar o marcar cada sugerencia, y FR-09 que cada sugerencia conserve su estado final. Las sugerencias IA ya existen (011-013) pero no hay forma de decidir sobre ellas ni de verlas agrupadas por ticket. Esta feature da el contrato backend que consumirá el panel de Fase 5 y alimenta las métricas de aceptación/edición/rechazo (spec §17.1).

## Criterios de aceptación

- [x] Modelo `app/models/feedback.py` (`Feedback`): `suggestion_id` (FK a `ai_suggestions`, ondelete CASCADE, único por sugerencia), `tenant_id`, `action` (`accepted|edited|rejected|flagged`), `reason`, `edited_content_hash`, timestamps; índice `(tenant_id, suggestion_id)`.
- [x] `AISuggestion.state` ampliado a `draft | accepted | edited | rejected | flagged` (FR-09).
- [x] `app/schemas/ai.py`: `FeedbackIn` (suggestion_id, action Literal, reason?, edited_content_hash?), `FeedbackOut`, `SuggestionOut` (id, type, state, confidence, model, prompt_version, output, created_at).
- [x] `app/services/feedback.py` — `FeedbackService.record()`: valida tenant/ticket/sugerencia (otro tenant o sugerencia inexistente → `PermissionError`), upsert de feedback, actualiza `AISuggestion.state`, audita `ai.feedback` (sin PII) y métrica `ai_feedback_total{action}`.
- [x] Rutas `app/api/routes_workspace.py`:
  - `POST /v1/ai/tickets/{ticket_id}/feedback` (`EDIT_RESPONSE`, §10.3): 404 otro tenant/ticket/sugerencia, 422 action inválido.
  - `GET /v1/ai/tickets/{ticket_id}/suggestions` (`READ_TICKETS`): lista sugerencias del ticket del tenant.
  - `GET /v1/workspace/my-tickets` (`READ_TICKETS`): tickets con `assignee_id = current_user.id` y estado `open|in_progress`, paginado, usando `TicketSummaryView` (sin PII pesada, 008).
- [x] `app/main.py`: router de workspace registrado.
- [x] Tests `tests/test_workspace.py`: feedback accepted/edited/rejected/flagged actualizan estado; feedback de otro tenant → 404; sugerencia inexistente → 404; action inválido → 422; listado de sugerencias por ticket (aislamiento por tenant); bandeja devuelve solo mis tickets; auditoría `ai.feedback` y métrica `ai_feedback_total`; suite completa sin regresión (`144 passed`).
- [x] Docs actualizados.

## Fuera de alcance

- UI del panel (frontend se especifica aparte; el backend expone los contratos).
- Envío de la respuesta al cliente (FR-04: humano; flujo de tickets 006).
- Admin de tenants y vistas de auditoría (016).
- Base de conocimiento / RAG (backlog).
