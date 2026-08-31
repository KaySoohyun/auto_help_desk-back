# 013 · Sugerencia de respuesta editable — Plan

_Cómo se implementa lo descrito en `spec.md`._

## Enfoque

Clon estructural de las features 011/012 (mismo pipeline: contexto redactado → orquestador → validación JSON → persistencia en `AISuggestion` → auditoría/métricas), cambiando la tarea, el prompt y la salida. Se reutiliza `TicketRepository`, `PiiRedactor` y `LLMOrchestrator`.

## Implementación

1. **Prompt `app/prompts/reply.py`**:
   - `REPLY_PROMPT_VERSION = "1.0.0"`.
   - `SYSTEM_REPLY`: rol (redactor de respuestas para agentes), reglas de tono profesional, grounding (basar solo en el contexto; no inventar políticas, precios, plazos ni compromisos), solo JSON.
   - `build_reply_user_prompt(subject, description, history, locale, tone)` con `TICKET_BLOCK` marcando el contenido como `DATOS_NO_CONFIABLES`.
   - Esquema JSON pedido: `suggestedReply`, `confidence`, `sources[]`, `policyFlags[]`, `warnings[]`.

2. **`app/services/reply_suggester.py`**:
   - `ReplyError(ValueError)`.
   - `ReplyResult` (dataclass): `suggested_reply`, `confidence`, `sources`, `policy_flags`, `warnings`.
   - `TicketReplySuggester` (mismo constructor que `TicketClassifier`/`TicketSummarizer`):
     - `suggest_reply(ticket_id, *, tone=None, language=None, trace_id=None)`:
       1. repositorio `get_or_none` + `list_messages` → `PermissionError` si otro tenant.
       2. redacta subject/description/history.
       3. `orchestrator.complete(task="reply", system=..., user=..., tenant_id, user_id, trace_id)`.
       4. parsea/valida JSON; `suggestedReply` requerido; `confidence` clamp [0,1]; `< threshold` → warning "revisión humana recomendada".
       5. persiste `AISuggestion(type='reply', output={suggested_reply, sources, policy_flags}, confidence, model, prompt_version, state='draft')`.
       6. audita `ai.replied` y métrica `ai_replies_total{status=ok}`.

3. **Schemas `app/schemas/ai.py`**: `SuggestedReplyOut` (suggested_reply, confidence, sources, policy_flags, warnings, suggestion_id, trace_id). `sources`/`policy_flags` como `list[str]` con default.

4. **Ruta `app/api/routes_ai.py`**: `POST /v1/ai/tickets/{ticket_id}/suggested-reply` (mismo patrón de mapeo de errores que classify/summary). Body opcional con `tone` y `language`.

5. **Tests `tests/test_reply.py`**:
   - `ReplyMock` (proveedor con salida JSON de respuesta válida, o configurable fail/bad_json/baja confianza).
   - Inyección del proveedor vía `monkeypatch` sobre `_effective_provider` (mismo fixture que classify/summary).
   - Casos: éxito; baja confianza → warning; otro tenant → 404; sin token → 401; LLM caído → 503; JSON inválido → 422; persistencia `type=reply` sin PII; auditoría `ai.replied` y métrica `ai_replies_total`.

## Riesgos

- **Repetir lógica de 011/012** — se mantiene el servicio separado (cada tarea tiene su prompt/validación propia); se comparte el patrón pero no se fuerza una clase base abstracta prematura.
- **PII en la respuesta** — el prompt no debe repetir datos del cliente; el test verifica que el `output` persistido no contenga el texto original de entrada.
- **Alucinación de políticas/precios** — el prompt prohíbe afirmaciones no verificables; `policy_flags` comunica qué aspectos no se pueden confirmar (FR-08).
- **Mock JSON**: usar proveedor mock especializado en tests (no tocar el mock general).
