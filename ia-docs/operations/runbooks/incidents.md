# Runbook · Incidentes

_Severidades: P1 = afecta a todos / seguridad; P2 = parcial; P3 = cosmético._

---

## LLM caído o degradado

**Severidad:** P1 si no hay fallback; P2 si solo degrada.

**Síntomas:**
- Alerta `llm_calls_total{status="unavailable"}` o latencia p95 alta.
- Endpoints IA devuelven 503 "LLM no disponible" o 429 de rate limit.

**Pasos:**
1. Verificar el proveedor (`LLM_PROVIDER`, `LLM_BASE_URL`): estado del servicio externo y credenciales en el gestor de secretos (no en `.env` de código).
2. Confirmar que los reintentos agotan (log `LLM agotó reintentos`); subir `LLM_MAX_RETRIES` o `LLM_RETRY_BACKOFF` solo como medida temporal.
3. Mientras tanto, activar el kill-switch si los 503 contaminan el tráfico: `AI_FEATURES_ENABLED=false` (ver `rollback.md`).
4. Correlacionar `X-Request-ID` con `audit_events.action = 'llm.call'`.
5. Tras recuperar el proveedor, subir un ping de prueba (`POST /v1/ai/ping`) y verificar `ok: true`.

---

## Prompt injection

**Severidad:** P1 (posible abuso de un agente o de un ticket malicioso).

**Síntomas:**
- `audit_events.action = 'llm.call'` con `result = 'alert'` y `detail.reasons = ['prompt_injection']`.
- Log `Posible prompt injection en entrada`.
- Incremento de `ai_guardrail_blocks_total{reason="prohibited_content"}`.

**Pasos:**
1. Identificar el ticket/tenant del evento por `trace_id` y `tenant_id`.
2. Revisar si la salida fue bloqueada (422 "Contenido bloqueado por política de seguridad"); si lo fue, el fallback seguro funcionó.
3. Si no se bloqueó y la salida fue sospechosa, invalidar la `AISuggestion` correspondiente y escalar.
4. Verificar que el contexto sigue delimitado como `DATOS_NO_CONFIABLES` (redacción PII de la 007 intacta).
5. Actualizar patrones en `GUARDRAIL_INJECTION_PATTERNS` si el vector es nuevo.

---

## Fuga de PII

**Severidad:** P1 (dato personal fuera del sistema o en un log).

**Síntomas:**
- `ai_guardrail_blocks_total{reason="pii_leak"}` en aumento.
- Un valor tokenizado aparece sin tokenizar en `audit_events.detail` o en logs.

**Pasos:**
1. Detener el sangrado: kill-switch (`AI_FEATURES_ENABLED=false`) o deshabilitar el tenant implicado (`TenantPolicy.ai_enabled=false`).
2. Localizar el alcance: qué campos de `audit_events`/logs tienen el valor original; el modelo debe guardar solo tokens.
3. Revocar/re-rotar cualquier valor comprometido (tokens de sesión si aplica).
4. Corregir el filtro de redacción (007) o del guardrail de salida y añadir test de regresión en `tests/test_pii.py`.
5. Notificar según política de retención (`ia_docs/architecture/05-politica-pii-retencion.md`).

---

## Rate limit excedido

**Severidad:** P2.

**Síntomas:**
- `http_errors_total{status="429"}` en aumento o eventos `llm.call` con `result = 'rate_limited'`.
- Un tenant concreto deja de recibir respuestas IA.

**Pasos:**
1. Identificar el tenant por la clave de rate limit (`tenant:user`) en los eventos auditados.
2. Si es un tenant legítimo sobrepasando el límite → subir `llm_rate_max_calls` vía `GlobalPolicy` (016/018), no en `.env` compartido.
3. Si es abuso → deshabilitar IA del tenant (`TenantPolicy.ai_enabled=false`) y revisar si hubo un bucle de regen.
4. Recordar que el rate limit es **en memoria por instancia**: en despliegue multi-instancia moverlo a Redis (documentado en `app/core/rate_limit.py`).
