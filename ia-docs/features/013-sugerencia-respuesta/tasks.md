# 013 · Sugerencia de respuesta editable — Tareas

_Checklist accionable derivada del `plan.md`._

- [x] Prompt versionado `app/prompts/reply.py` (`REPLY_PROMPT_VERSION=1.0.0`, SYSTEM + builder con separación datos/instrucciones y reglas de grounding).
- [x] `app/services/reply_suggester.py`: `ReplyError`, `ReplyResult`, `TicketReplySuggester.suggest_reply()` (contexto redactado, orquestador, validación JSON, persistencia, auditoría y métricas).
- [x] Schemas `app/schemas/ai.py`: `SuggestedReplyOut`.
- [x] Ruta `POST /v1/ai/tickets/{ticket_id}/suggested-reply` (REQUEST_AI_SUGGESTION) con 404 otro tenant, 429/503/422 mapeados.
- [x] Tests `tests/test_reply.py`: éxito, baja confianza→warnings, otro tenant→404, 401, LLM caído→503, JSON inválido→422, persistencia sin PII, auditoría y métricas.
- [x] Ejecutar suite completa sin regresión (`123 passed`).
- [x] Actualizar `ia_docs/cambios.md`, `roadmap.md` y spec/plan/tasks.

## Notas

- Mismo pipeline que 011/012: redacción PII (007) → orquestador (010) → `AISuggestion` (draft, sin PII) → auditoría/métricas.
- La tabla `ai_suggestions` ya soporta `type='reply'` (creada en 011).
- Grounding solo sobre ticket/historial (FR-08): la base de conocimiento por tenant queda fuera de alcance (backlog).
