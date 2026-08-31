# 009 · Observabilidad del backend — Plan

_Cómo se implementa lo descrito en `spec.md`._

## Enfoque

Sin dependencias externas (regla: no inventar; el venv no tiene prometheus-client ni OpenTelemetry). Se construye un registro de métricas en memoria con stdlib (`collections`, `time`), un middleware FastAPI que mide latencia y captura errores/status, un logger de aplicación con `trace_id`, y un endpoint `/v1/metrics` protegido que serializa el registro en formato de texto Prometheus a mano.

## Implementación

1. **`app/core/metrics.py`**
   - `class MetricsRegistry`: registros en memoria con contadores (`inc(name, labels, value)`), gauge y histograma (`observe(name, value, labels)` con buckets fijos tipo Prometheus: .005, .01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10).
   - Métodos `counter`, `histogram`, `gauge` tipados; thread-safe con `threading.Lock`.
   - `render_prometheus() -> str`: genera `# TYPE name kind` y `name{label="value"} valor` (y `_bucket/_sum/_count` para histograms) en orden estable.
   - Instancia global `metrics` reutilizable y reseteable en tests.
   - Nombres por norma Prometheus: `http_requests_total`, `http_request_duration_seconds`, `http_responses_total{status}`, `http_exceptions_total`, `tickets_created_total`, `tickets_closed_total`.

2. **`app/core/logging.py`**
   - Configura `logging.basicConfig` formateado con timestamp, nivel, `trace_id` (get del ContextVar vía `get_trace_id`) y mensaje; applogger de módulo.
   - `logger = logging.getLogger("app")`; helpers `log_request_error`, `log_exception`.

3. **Middleware/Observación en `app/api/observability.py`**
   - `MetricsMiddleware(BaseHTTPMiddleware)`: al terminar la respuesta, inc `http_requests_total` con `method`, `route` (o `path` base si no hay route) y `status`; registra duración en `http_request_duration_seconds`; si status ≥ 400 incrementa `http_errors_total{status_code}`.
   - `request_id`: reutilizar `get_trace_id` para `X-Request-ID`/`trace_id` en `STATE` y headers de respuesta.
   - Manejo de excepciones: `healthcheck`/ejcepcion handler que loggea con trace_id y cuenta `http_exceptions_total` (sin exponer PII ni stack sensible en la respuesta).

4. **Ruta `/v1/metrics`** en `app/api/routes_metrics.py`:
   - `GET /v1/metrics` con `require_permissions(VIEW_* ...)`. Dado que no existe `VIEW_METRICS`, usar el permiso existente `VIEW_AUDIT` o `PLATFORM_ADMIN` (se valida decisión con usuario). Retorna `text/plain` con `metrics.to_prometheus()`.
   - Excluido del middleware? No: el middleware midetodos; se documenta que `/metrics` también aparece (teórico ok). El prefijo de ruta se usa como `route` label.

5. **Métricas de negocio** (bajo costo, sin PII):
   - En `TicketRepository.create` (o en la ruta) se llam `metrics.inc("tickets_created_total", {"tenant_id": ...})`.
   - En el cierre (`routes_tickets.close`) `tickets_closed_total`.

6. **Tests `tests/test_metrics.py`**:
   - Suite: resetear registro antes de cada test.
   - `GET /v1/metrics` sin token → 401; con token sin rol → 403; con rol adecuado → 200 y `text/plain`.
   - Hacer requests reales a `/v1/tickets` (con token) y comprobar que `http_requests_total`, `http_request_duration_seconds` (duración > 0) y `http_errors_total` si se fuerza 404; y que `tickets_created_total` crece tras crear, `tickets_closed_total` tras cerrar.
   - Test de no-PII: render de métricas no contiene el asunto/descripción/body ni el email del usuario.
   - Test de formato Prometheus: `# TYPE name kind`, `name_bucket{le="..."}` mínimo.
   - Suite completa sin regresión.

## Riesgos

- **BaseHTTPMiddleware + streaming**: con `StreamingResponse` hay que capturar duración en el `finally`. Se mide tiempo total.
- **Etiquetas**: `path` label sin query (usar `request.url.path` normalizado a ruta template con `request.scope.get("route")` name. Si no hay route (404), usar el path). Esto evita cardinalidad infinita.
- **Sin deps**: Prometheus real se integra en feature 018 (deploy); el formato de texto es compatible.
- **Permiso del endpoint**: no existe `VIEW_METRICS`; propuesta: usar rol `PLATFORM_ADMIN` (feature 003 RBAC). Documentarlo y confirmar con el usuario.