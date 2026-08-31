# 011 · Clasificación automática de tickets — Tareas

_Checklist accionable derivada del `plan.md`._

- [x] Modelo `AISuggestion` (`app/models/ai_suggestion.py`) con índice `(tenant_id, ticket_id)`.
- [x] Config: `ai_confidence_threshold`, catálogo de categorías e intenciones en `app/core/config.py`.
- [x] Prompt versionado `app/prompts/classification.py` (`CLASSIFY_PROMPT_VERSION=1.0.0`, SYSTEM + builder con separación datos/instrucciones).
- [x] `app/services/classifier.py`: `ClassificationError`, `ClassificationResult`, `TicketClassifier.classify()` (contexto redactado, llamada orquestador, validación JSON, persistencia, auditoría y métricas).
- [x] Schemas `app/schemas/ai.py`: `ClassificationOut`.
- [x] Ruta `POST /v1/ai/tickets/{ticket_id}/classify` (REQUEST_AI_SUGGESTION) con 404 otro tenant, 429/503/422 mapeados.
- [x] Registrar router en `main.py` (ruta dentro del router de IA ya registrado).
- [x] Tests `tests/test_classify.py`: éxito, baja confianza→warnings, otro tenant→404, 401, LLM caído→503, JSON inválido→422, persistencia sin PII, auditoría y métricas.
- [x] Ejecutar suite completa sin regresión (`106 passed`).
- [x] Actualizar `ia_docs/cambios.md`, `roadmap.md` y spec/plan/tasks.

## Notas

- Reutiliza `PiiRedactor` (007) para redactar contexto antes del LLM; el `output` persistido nunca contiene el texto original.
- La tabla `ai_suggestions` servirá también para 012 (summary) y 013 (reply).
- La clasificación NO se aplica sola al ticket; queda como sugerencia `draft` editable (feedback en feature 015).
- En tests se inyecta el proveedor vía `monkeypatch` de `_effective_provider` (evita fuga global entre tests).