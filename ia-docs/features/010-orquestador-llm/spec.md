# 010 · Orquestador LLM y conectores de IA

**Estado:** implementado

## Qué hace

Implementa el **punto único de integración con LLM** (ADR-002, spec §14.2, épica 4.1): un gateway centralizado dentro del backend que orquesta las llamadas a un proveedor/LLM con:

- **Selección de modelo por tarea** — mapeo task → modelo con override explícito (`model` puede indicar falla).
- **Timeout** configurable por llamada.
- **Reintentos** con backoff (errores 5xx/timeout/429 del proveedor).
- **Límites de uso** (rate limit por usuario+tenant en ventana de tiempo) — sin Redis (no está en el stack): bucketing en memoria con reset.
- **Fallback seguro**: si el LLM no responde tras reintentos, se dispara una excepción controlada `LLMUnavailableError` (la feature 013 decide el fallback de respuesta) y se registra incidente. Nunca se bloquea el request del ticket; la aplicación sigue funcionando manualmente.
- **Métricas**: tokens, latencia, errores por tarea, usando el `MetricsRegistry` de la feature 009 (`llm_calls_total`, `llm_latency_seconds`, `llm_tokens_total`, `llm_errors_total`).
- **Auditoría**: cada llamada LLM se audita (service `llm`, acción `llm.call`) con modelo, resultado, tokens y latencia; nunca el contenido del prompt ni la respuesta.
- **Redacción previa**: el orquestador recibe **contexto ya redactado** (la PII se redacta en la capa que use este módulo, feature 007/011). El orquestador no recibe PII cruda.

Se usa `httpx` (dependencia ya instalada) contra un endpoint HTTP OpenAI-compatible, con un modo `mock` (proveedor simulado determinista) para desarrollo/reste y para que la suite no dependa de red ni de credenciales.

## Por qué

Es el requisito base de la Fase 4 (épica 4.1). Todas las tareas de IA (clasificar 011, resumir 012, sugerir 013, guardrails 014) consumirán este orquestador. Centraliza costos, límites y errores en un solo lugar, evita duplicación y cumple ADR-002.

## Criterios de aceptación

- [ ] `app/services/llm.py`: data estructura de respuesta `LLMResponse` (`content`, `model`, `usage {prompt_tokens, completion_tokens}`, `duration_seconds`) y error `LLMUnavailableError`.
- [ ] Proveedor HTTP (`HTTPLLMProvider`) vía `httpx`, compatible con endpoint OpenAI (`POST /v1/chat/completions`) con `Authorization: Bearer <api_key>`; configurable por env (`LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES`, `LLM_RETRY_BACKOFF`, `LLM_MAX_TOKENS`).
- [ ] Proveedor mock (`MockLLMProvider`) para tests/dev: devuelve JSON determinista según la tarea; configurable.
- [ ] Fábrica `get_llm_provider(settings)` que elige según `LLM_PROVIDER=mock|http` (default `mock`).
- [ ] `app/core/rate_limit.py`: `RateLimitStore` en memoria, clave `tenant_id:user_id`, ventana configurable (`LLM_RATE_LIMIT_WINDOW_SECONDS`, `LLM_RATE_MAX_CALLS`); devuelve falso cuando se excede.
- [ ] `LLMOrchestrator` (`app/services/llm_orchestrator.py`) con método `complete(task, system, user, model=None)`:
  - valida rate limit → `LLMRateLimitExceeded` (HTTP 429 si va a endpoint);
  - llama al proveedor con timeout; reintenta con backoff; aagrupa 429/5xx/no-responsive como `LLMUnavailableError`;
  - registra métricas (`llm_calls_total{task,status}`, `llm_latency_seconds`, `llm_tokens_total{task}`) y auditoría (`llm.call`);
  - devuelve `LLMResponse`.
- [ ] Router `app/api/routes_ai.py`: `POST /v1/ai/ping` (protegido con `REQUEST_AI_SUGGESTION`, sin PII) que invoca al orquestador con un prompt mínimo de conectividad y devuelve `{ok, model, latency_ms}`; `GET /v1/ai/info` (protegido con `VIEW_AUDIT`) con config no sensible (model, provider, limits).
- [ ] Errores: 429 si rate limit, 503 con `LLMUnavailableError` (si llega), 401/403 del RBAC.
- [ ] Sin secretos en código ni en logs (api_key solo env).
- [ ] Tests: proveedor mock determinista, rate limit, retry+backoff exitoso (mock de httpx con 500 → success), timeout→`LLMUnavailableError` → 503, métricas y auditoría se registran, `/v1/ai/ping` 401/403 y con mock devuelve ok, `/v1/ai/config` protegido.
- [ ] Suite completa pasa sin regresión.
- [ ] Docs actualizados (`cambios.md`, `roadmap.md`), spec/plan/tasks marcados.

## Fuera de alcance

- Clasificación/resumen/sugerencia reales (features 011-013) — aquí solo el gateway.
- Guardrails de entrada/salida (prompt injection, alucinación) → feature 014.
- Múltiples proveedores simultáneos (ADR-002 difiere multi-proveedor); la abstracción permite añadir.
- Base de conocimiento / RAG → feature futura.
- Redis para rate limit (solo memoria en este MVP; documentado para prod).