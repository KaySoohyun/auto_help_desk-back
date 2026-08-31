# Alertas base

_Reglas sugeridas sobre `GET /v1/metrics` (feature 009) y la tabla `audit_events`. Severidad: `critical` (página), `warning` (bandeja), `info` (observación)._

## 1. LLM caído o degradado — `critical`

```promql
sum(rate(llm_calls_total{status="unavailable"}[5m])) > 0
```

Síntoma: el proveedor no responde o agota reintentos (`LLMUnavailableError` → 503 en los endpoints IA). Ver runbook "LLM caído". Los 503 no rompen la gestión de tickets.

## 2. Latencia LLM alta — `warning`

```promql
histogram_quantile(0.95, sum(rate(llm_latency_seconds_bucket[5m])) by (le, task)) > 20
```

Umbral a calibrar con el proveedor. Precede a timeouts y a los reintentos.

## 3. Errores HTTP 5xx — `critical`

```promql
sum(rate(http_errors_total{status=~"5.."}[5m])) > 0.5
```

## 4. Excepciones no controladas — `critical`

```promql
sum(increase(http_exceptions_total[5m])) > 0
```

Suelen implicar un bug real: abrir incidente y correlacionar con `X-Request-ID`.

## 5. Bloqueos de guardrails — `warning`

```promql
sum(increase(ai_guardrail_blocks_total[1h])) > 5
```

Puede indicar un patrón de salida del LLM (jailbreak) o un falso positivo del filtro. Revisar razones:

```promql
sum by (reason) (increase(ai_guardrail_blocks_total[1h]))
```

## 6. Rate limit excedido — `warning`

Sin métrica dedicada: alertar sobre el equivalente auditable y el 429.

```promql
sum(increase(http_errors_total{status="429"}[15m])) > 10
```

Complementar con auditoría:

```sql
SELECT count(*) FROM audit_events
WHERE action = 'llm.call' AND result = 'rate_limited' AND created_at > now() - interval '15 minutes';
```

## 7. Kill-switch activado — `critical`

```promql
sum(increase(ai_disabled_total[5m])) > 0
```

La IA está globalmente deshabilitada (`AI_FEATURES_ENABLED=false`): verificar si es intencional. Los endpoints devuelven 503.

## 8. Tenant deshabilitado — `info`

```promql
sum(increase(ai_tenant_disabled_total[1h])) > 0
```

Rollout por tenant funcionando (403 a ese tenant). Informa quién lo está consumiendo por error:

```sql
SELECT tenant_id, count(*) FROM audit_events
WHERE action = 'ai.tenant_disabled' AND created_at > now() - interval '1 hour'
GROUP BY tenant_id;
```

## 9. PII en auditoría o logs — `critical`

No hay métrica: monitorear el runbook de "fuga de PII". Chequear que ningún valor original aparece en `audit_events.detail` (debe estar tokenizado).

## Operación de alertas

- Toda alerta `critical` dispara el runbook correspondiente y una entrada en `audit_events` (acción `ops.alert`, result `critical`).
- Alertas `warning` se revisan en el daily; las que se repiten 3 días seguidos se escalan a `critical`.
- Los umbrales se ajustan con datos reales del dashboard; los de arriba son puntos de partida conservadores.
