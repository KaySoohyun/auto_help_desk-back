# 012 · Resumen automático de tickets — Tareas

_Checklist accionable derivada del `plan.md`._

- [x] Prompt versionado `app/prompts/summary.py` (`SUMMARY_PROMPT_VERSION=1.0.0`, SYSTEM + builder con separación datos/instrucciones).
- [x] `app/services/summarizer.py`: `SummaryError`, `SummaryResult`, `TicketSummarizer.summarize()` (contexto redactado, orquestador, validación JSON, persistencia, auditoría y métricas).
- [x] Schemas `app/schemas/ai.py`: `SummaryOut`.
- [x] Ruta `POST /v1/ai/tickets/{ticket_id}/summary` (REQUEST_AI_SUGGESTION) con 404 otro tenant, 429/503/422 mapeados.
- [x] Tests `tests/test_summary.py`: éxito, baja confianza→warnings, otro tenant→404, 401, LLM caído→503, JSON inválido→422, persistencia sin PII, auditoría y métricas.
- [x] Ejecutar suite completa sin regresión (`114 passed`).
- [x] Actualizar `ia_docs/cambios.md`, `roadmap.md` y spec/plan/tasks.

## Notas

- Mismo pipeline que 011: redacción PII (007) → orquestador (010) → `AISuggestion` (draft, sin PII) → auditoría/métricas.
- La tabla `ai_suggestions` ya soporta `type='summary'` (creada en 011).