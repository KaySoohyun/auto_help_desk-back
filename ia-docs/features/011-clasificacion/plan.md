# 011 · Clasificación automática de tickets — Plan

_Cómo se implementa lo descrito en `spec.md`._

## Enfoque

Feature de negocio sobre el orquestador LLM (010): un servicio `TicketClassifier` que arma el contexto redactado del ticket, invoca la tarea `classify`, valida la salida JSON estructurada y persiste una `AISuggestion`. Todo con el mismo patrón de auditoría y métricas ya usado en features anteriores.

## Implementación

1. **Modelo `app/models/ai_suggestion.py`** (`AISuggestion`):
   - `id`, `tenant_id` (String 64, index), `ticket_id` (FK tickets ondelete CASCADE), `type` (String 32: `classification|summary|reply`), `output` (JSON — sin PII), `confidence` (Float nullable), `model` (String 128), `prompt_version` (String 32), `state` (String 20 default `draft`), `created_at`, `updated_at`.
   - Índice compuesto `(tenant_id, ticket_id)`.

2. **Config**: `ai_confidence_threshold: float = 0.6`, `ai_classify_categories: str` (catálogo por defecto separado por comas) y `ai_classify_intents: str`.

3. **Prompt versionado** (`app/prompts/classification.py`):
   - `CLASSIFY_PROMPT_VERSION = "1.0.0"`.
   - `SYSTEM_CLASSIFY`: rol, reglas (solo JSON, categorías permitidas, prioridades `low|medium|high|urgent`, no inventar), comportamiento ante falta de datos.
   - `build_classify_user_prompt(subject, description, history, locale, allowed_categories)` con el contenido del ticket marcado como `DATOS_NO_CONFIABLES` (guardrail de separación, §12).

4. **`app/services/classifier.py`**:
   - `ClassificationError(ValueError)`.
   - `ClassificationResult` (dataclass): category, subcategory, intent, suggested_priority, confidence, rationale, warnings.
   - `TicketClassifier`:
     - `classify(ticket_id, *, user, db, audit, orchestrator, trace_id)`:
       1. `get_ticket` (repositorio) con tenant check → PermissionError → 404 (patrón rutas_tickets).
       2. Cargar mensajes descifrados (hasta N últimos).
       3. `PiiRedactor` sobre subject/description/historial (modo redact).
       4. `orchestrator.complete(task="classify", system=SYSTEM_CLASSIFY, user=build_..., tenant_id, user_id, trace_id)`.
       5. Parsear JSON (`json.loads`), validar campos y prioridad contra `low|medium|high|urgent`; si falla → `ClassificationError`.
       6. `confidence` fuera de [0,1] → clamp; si `< threshold` añadir warning "revisión humana recomendada".
       7. Persistir `AISuggestion(type='classification', output={...}, confidence, model, prompt_version, state='draft')`; commit.
       8. Auditar `ai.classified` (result, category, priority, confidence, model, prompt_version; sin textos) y métricas `ai_classifications_total{status=ok}`.

5. **Schemas `app/schemas/ai.py`**: `ClassificationOut` con los campos de §15.1 + `suggestionId` y `traceId`.

6. **Ruta `app/api/routes_classify.py`** (o dentro de `routes_ai.py`):
   - `POST /v1/ai/tickets/{ticket_id}/classify` con `require_permissions(REQUEST_AI_SUGGESTION)`.
   - Otro tenant → 404 (repositorio).
   - Mapeo de errores: `LLMRateLimitExceeded` → 429, `LLMUnavailableError` → 503, `ClassificationError` → 422.
   - Auditoría y métricas delegadas al servicio.

7. **Tests `tests/test_classify.py`**:
   - Mock determinista: se configura para que el JSON de clasificación salga válido; verificar 200 y campos de salida.
   - Baja confianza → warnings con "revisión humana".
   - Otro tenant → 404; sin token → 401; rol sin permiso → 403 (verificar si existe rol sin REQUEST_AI_SUGGESTION; si todos lo tienen, probar solo 401/404).
   - LLM caído (mock failure) → 503.
   - JSON inválido (mock que devuelve texto no-JSON) → 422.
   - Persistencia: `AISuggestion` en DB con type classification y sin PII en `output`.
   - Auditoría `ai.classified` y métrica `ai_classifications_total`.
   - Suite completa sin regresión.

## Riesgos

- **Mock JSON**: el `MockLLMProvider` actual devuelve `{"ok": true, "task": "mock"}`. Para clasificar, el test necesita un mock con salida de clasificación. Se usa un proveedor mock especializado en tests (no tocar el mock general).
- **Categorías**: el catálogo por defecto queda en config (lista documentada); la salida se valida contra prioridades pero la categoría se deja libre con longitud máxima (para no romper tenants con catálogos propios).
- **Sin PII**: se redacta antes de enviar; `output` persistido no contiene el texto original; tests lo verifican.
- **Deferred description**: al cargar el ticket para clasificar hay que acceder a `description` dentro de la sesión (patrón feature 008).