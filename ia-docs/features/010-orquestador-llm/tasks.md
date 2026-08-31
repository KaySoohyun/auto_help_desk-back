# 010 · Orquestador LLM y conectores de IA — Tareas

_Checklist accionable derivada del `plan.md`._

- [x] Añadir settings LLM en `app/core/config.py` (provider, base_url, api_key `SecretStr`, model, timeout, retries, backoff, max_tokens, rate limits).
- [x] Crear `app/services/llm.py`: `LLMUsage`, `LLMResponse`, `LLMUnavailableError`, `LLMRateLimitExceeded`, `BaseLLMProvider`, `HTTPLLMProvider`, `MockLLMProvider`, fábrica `get_llm_provider`.
- [x] Crear `app/core/rate_limit.py`: `RateLimitStore` en memoria (ventana deslizante, lock).
- [x] Crear `app/services/llm_orchestrator.py`: `LLMOrchestrator.complete()` con rate limit, retry+backoff, métricas y auditoría.
- [x] Crear `app/api/routes_ai.py`: `POST /v1/ai/ping` (REQUEST_AI_SUGGESTION) y `GET /v1/ai/info` (VIEW_AUDIT); registrar router en `main.py`.
- [x] Tests `tests/test_llm.py`: mock determinista, rate limit, retry→éxito, timeout→503, 401/403, métricas y auditoría, reset entre tests.
- [x] Ejecutar suite completa sin regresión (`98 passed`).
- [x] Actualizar `ia_docs/cambios.md`, `roadmap.md` y spec/plan/tasks (estado implementado).

## Notas

- No SDKs de proveedores: `httpx` + formato OpenAI Chat Completions.
- Rate limit en memoria (sin Redis) con reset en tests; la clave es `tenant_id:user_id`.
- El orquestador nunca guarda/audita el contenido del prompt ni la respuesta; solo métricas y metadata.
- `POST /v1/ai/ping`: con `LLM_PROVIDER=mock` (default) responde 200 sin red; con `http` y LLM caído → 503.