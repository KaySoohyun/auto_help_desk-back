# 012 · Resumen automático de tickets — Plan

_Cómo se implementa lo descrito en `spec.md`._

## Enfoque

Clon estructural de la feature 011 (mismo pipeline: contexto redactado → orquestador → validación JSON → persistencia en `AISuggestion` → auditoría/métricas), cambiando la tarea y el prompt. Se reutiliza `TicketRepository`, `PiiRedactor` y `LLMOrchestrator`.

## Implementación

1. **Prompt `app/prompts/summary.py`**:
   - `SUMMARY_PROMPT_VERSION = "1.0.0"`.
   - `SYSTEM_SUMMARIZE`: rol, reglas (resumen breve y accionable, sin datos innecesarios del cliente, solo JSON), comportamiento ante falta de datos.
   - `build_summary_user_prompt(subject, description, history, locale)` con `TICKET_BLOCK` marcando el contenido como `DATOS_NO_CONFIABLES`.

2. **`app/services/summarizer.py`**:
   - `SummaryError(ValueError)`.
   - `SummaryResult` (dataclass): `summary`, `missing_information`, `confidence`, `warnings`.
   - `TicketSummarizer` (mismo constructor que `TicketClassifier`: db, user_id, tenant_id, orchestrator, audit):
     - `summarize(ticket_id, *, trace_id)`:
       1. repositorio `get_or_none` + `list_messages` → `PermissionError` si otro tenant.
       2. redacta subject/description/history.
       3. `orchestrator.complete(task="summary", system=..., user=..., tenant_id, user_id, trace_id)`.
       4. parsea/valida JSON; `summary` requerido; `confidence` clamp [0,1]; `< threshold` → warning "revisión humana recomendada".
       5. persiste `AISuggestion(type='summary', output={summary, missing_information}, confidence, model, prompt_version, state='draft')`.
       6. audita `ai.summarized` y métrica `ai_summaries_total{status=ok}`.

3. **Schemas `app/schemas/ai.py`**: `SummaryOut` (summary, missing_information, confidence, warnings, suggestion_id, trace_id).

4. **Ruta `app/api/routes_ai.py`**: `POST /v1/ai/tickets/{ticket_id}/summary` (mismo patrón de mapeo de errores que classify).

5. **Tests `tests/test_summary.py`**:
   - `SummaryMock` (proveedor con salida JSON de resumen válida, o configurable fail/bad_json/baja confianza).
   - Inyección del proveedor vía `monkeypatch` sobre `_effective_provider` (mismo fixture que classify).
   - Casos: éxito; baja confianza → warning; otro tenant → 404; sin token → 401; LLM caído → 503; JSON inválido → 422; persistencia `type=summary` sin PII; auditoría `ai.summarized` y métrica `ai_summaries_total`.

## Riesgos

- **Repetir lógica de 011** — se mantiene el servicio separado (cada tarea tiene su prompt/validación propia); se comparte el patrón pero no se fuerza una clase base abstracta prematura.
- **PII en resumen** — el resumen generado podría repetir datos del ticket; el test verifica que el `output` persistido no contenga el texto original de entrada (el LLM mock devuelve texto fijo sin PII).
- **Mock JSON**: usar proveedor mock especializado en tests (no tocar el mock general).