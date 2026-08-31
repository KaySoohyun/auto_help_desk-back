# Dashboard de operación

_Fuente de métricas: `GET /v1/metrics` (formato de texto Prometheus), protegido con el permiso `VIEW_AUDIT` (feature 009). Sin dependencias externas._

## Inventario de métricas

### HTTP / aplicación (feature 009)

| Métrica | Tipo | Labels | Descripción |
| --- | --- | --- | --- |
| `http_requests_total` | counter | `method`, `route`, `status` | Requests totales por ruta/status. |
| `http_request_duration_seconds` | histogram | `method`, `route` | Latencia por ruta (buckets default). |
| `http_errors_total` | counter | `status` | Errores HTTP (≥400). |
| `http_exceptions_total` | counter | `method`, `route` | Excepciones no controladas. |

### IA (features 010-016, 018)

| Métrica | Tipo | Labels | Descripción |
| --- | --- | --- | --- |
| `llm_calls_total` | counter | `task`, `status` (`ok`/`error`/`unavailable`) | Llamadas LLM por tarea. |
| `llm_tokens_total` | counter | `task` | Tokens consumidos. |
| `llm_latency_seconds` | histogram | `task` | Latencia del proveedor LLM. |
| `ai_guardrail_blocks_total` | counter | `reason`, `task` | Salidas bloqueadas por guardrails (014). |
| `ai_classifications_total` | counter | `status` | Clasificaciones generadas (011). |
| `ai_summaries_total` | counter | `status` | Resúmenes generados (012). |
| `ai_replies_total` | counter | `status` | Respuestas sugeridas (013). |
| `ai_feedback_total` | counter | `action` | Feedback del agente (015). |
| `ai_disabled_total` | counter | — | Llamadas rechazadas por kill-switch (018). |
| `ai_tenant_disabled_total` | counter | — | Llamadas rechazadas por política de tenant (018). |

### Negocio de tickets (009)

| Métrica | Tipo | Labels | Descripción |
| --- | --- | --- | --- |
| `tickets_created_total` | counter | `tenant_id` | Tickets creados por tenant. |
| `tickets_closed_total` | counter | `tenant_id` | Tickets cerrados por tenant. |

## Paneles sugeridos

### 1. Salud del servicio

```promql
rate(http_requests_total{status=~"5.."}[5m])
rate(http_exceptions_total[5m])
# Latencia p95 por ruta
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, route))
```

### 2. Salud del LLM

```promql
rate(llm_calls_total{status="unavailable"}[5m])
# p95 de latencia LLM
histogram_quantile(0.95, sum(rate(llm_latency_seconds_bucket[5m])) by (le, task))
rate(llm_tokens_total[5m])
```

### 3. Seguridad y guardrails

```promql
increase(ai_guardrail_blocks_total[1h])
increase(ai_disabled_total[1h])
increase(ai_tenant_disabled_total[1h])
# Detalle de bloqueos por motivo
sum by (reason) (increase(ai_guardrail_blocks_total[24h]))
```

### 4. Uso de IA por task

```promql
sum by (task) (increase(ai_classifications_total[1h]))
sum by (task) (increase(ai_summaries_total[1h]))
sum by (task) (increase(ai_replies_total[1h]))
# Feedback del agente: tasa de aceptación/rechazo
sum by (action) (rate(ai_feedback_total[24h]))
```

### 5. Tenants

```promql
sum by (tenant_id) (rate(tickets_created_total[1h]))
sum by (tenant_id) (rate(tickets_closed_total[1h]))
```

## Notas de operación

- Las métricas son **en memoria** por instancia: con más de una instancia, scrapear `GET /v1/metrics` de cada una (Prometheus `honor_labels` para evitar colisiones). El rate limit por tenant también es en memoria (ver runbook de rate limit).
- El `X-Request-ID` de cada respuesta permite correlacionar un request con su evento de auditoría (`audit_events.trace_id`).
- La consola de auditoría de la 016 complementa el dashboard: eventos `ai.disabled`, `ai.tenant_disabled`, `llm.call` y `ai_guardrail_blocks_total` tienen su equivalente auditable en `audit_events`.
