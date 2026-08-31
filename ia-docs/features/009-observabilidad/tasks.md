# 009 · Observabilidad del backend — Tareas

_Checklist accionable derivada del `plan.md`._

- [x] Crear `app/core/metrics.py` con `MetricsRegistry` (counter, gauge, histogram + buckets) y `render_prometheus()`.
- [x] Crear instancia global `metrics` con reset para tests.
- [x] Configurar `app/core/logging.py` con formateo `trace_id`/nivel y applogger.
- [x] Crear `MetricsMiddleware` en `app/core/observability.py`: mide duración, cuenta `http_requests_total` por método/ruta/status, histograma de latencia, errores ≥400 (`http_errors_total`) y excepciones (`http_exceptions_total`).
- [x] Manejo de exceptions/trace_id sin PII (no loggear body ni auth) — integrado con `metrics` y set de `trace_id` por request.
- [x] Ruta `GET /v1/metrics` con `require_permissions(VIEW_AUDIT)` que devuelve texto Prometheus (`text/plain`).
- [x] Métricas de negocio: inc `tickets_created_total` y `tickets_closed_total` (tenant_id) en las rutas de tickets.
- [x] Registrar router y middleware en `main.py`.
- [x] Tests `tests/test_metrics.py`: 401/403/200, contadores e histograma crecen tras requests reales, errores incrementan, formato Prometheus, no-PII en el render, reset entre tests.
- [x] Ejecutar suite completa de tests sin regresión (`85 passed`).
- [x] Actualizar `ia_docs/cambios.md`, `roadmap.md` (009 Hecho) y `spec/plan/tasks`.

## Notas

- Endpoint protegido con `VIEW_AUDIT` (permiso existente del catálogo RBAC; no se agregó `VIEW_METRICS`).
- Label de ruta: route template si existe; si no, `url.path` base (evita cardinalidad alta por query/IDs).
- Sin dependencias externas (stdlib + FastAPI/Starlette): formato de texto Prometheus escrito a mano para ser scrape-able por Prometheus en despliegue.