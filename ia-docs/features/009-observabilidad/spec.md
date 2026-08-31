# 009 · Observabilidad del backend

**Estado:** implementado

## Qué hace

Capa de observabilidad (Fase 3, épica 3.5 del plan de ejecución) que expone métricas, latencias, errores y traceabilidad del backend, cumpliendo el §14.4 del spec (trazas, métricas de latencia, errores, uso y alertas de seguridad):

- **Métricas de HTTP**: contadores por método/endpoint/status y histogramas de latencia.
- **Métricas de errores**: contador de excepciones y de 4xx/5xx.
- **Métricas de negocio de bajo costo**: tickets creados/cerrados por tenant (sin PII).
- **Trazabilidad**: logging con `trace_id` generado por request (ya existe `get_trace_id` en `deps`); se centraliza en un logger de aplicación.
- **Exposición**: endpoint `/v1/metrics` en formato texto compatible con Prometheus (sin dependencias: se escribe el formato a mano), protegido por RBAC.

## Por qué

Es requisito del spec §14.4 y de la arquitectura (D-05/§16). Permite detectar degradación, errores y picos de uso antes que los usuarios. Como no hay dependencias de observabilidad en el stack (se prohíbe inventar), se implementa un recolector mínimo a medida con stdlib, listo para integrarse con Prometheus/Grafana en despliegue (feature 018).

## Criterios de aceptación

- [ ] Existe `MetricsRegistry` en memoria (counter/gauge/histogram) sin dependencias externas.
- [ ] Middleware registra para cada request: método, ruta base, status, duración; guarda histograma de latencia y contadores.
- [ ] Se registra un contador de errores (4xx/5xx) y de excepciones no controladas.
- [ ] `GET /v1/metrics` devuelve texto en formato Prometheus (`# TYPE name kind`, `name{label="v"} value`).
- [ ] `/v1/metrics` está protegido con `require_permissions(VIEW_AUDIT)` o rol plataforma; sin token → 401, sin rol → 403.
- [ ] El logging incluye `trace_id` (via `get_trace_id`) y categoría de error — sin PII (no se loggea body ni auth).
- [ ] Métricas de negocio: contadores de tickets creados y cerrados (tenant_id del token).
- [ ] Tests: valores se incrementan tras requests reales (hits, duración>0, status observado), /metrics protegido (401/403), format of Prometheus, los errores incrementan counters, y no hay PII en las métricas.

## Fuera de alcance

- Prometheus/Grafana/Alerta reales (infra; documentado en feature 018 CI/CD).
- Trazas distribuidas OTLP/OpenTelemetry (se documenta; el trace_id solo loggable local).
- Métricas de IA (tokens, costos, latencia del LLM) → feature 010 (orquestador).
- Dashboard y alertas (dependen del deploy).