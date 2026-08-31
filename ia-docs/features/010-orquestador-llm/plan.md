# 010 · Orquestador LLM y conectores de IA — Plan

_Cómo se implementa lo descrito en `spec.md`._

## Enfoque

Sin SDKs de proveedores (no están en el stack): se usa `httpx` (ya instalado) contra un endpoint HTTP compatible con OpenAI Chat Completions. Se define un `Protocol`-like mínimo para que cambiar el proveedor no toque el resto. En desarrollo/reste se usa un proveedor mock determinista para que la suite no dependa de red ni credenciales. Rate limit en memoria (sin Redis) con ventana fija.

## Implementación

1. **`app/services/llm.py`**
   - `LLMUsage` (dataclass: prompt_tokens, completion_tokens) y `LLMResponse` (dataclass: content, model, usage, duration_seconds).
   - `LLMUnavailableError(RuntimeError)` y `LLMRateLimitExceeded(HTTPException 429)` (este último como excepción FastAPI para endpoint).
   - `BaseLLMProvider` con método `complete(messages, model, max_tokens, temperature) -> LLMResponse`. Implementaciones:
     - `HTTPLLMProvider`: usa `httpx.Client` con `timeout`; envía `POST {base_url}/v1/chat/completions`, header `Authorization: Bearer <api_key>`, body `{"model":..., "messages":..., "max_tokens":..., "temperature":...}`; parsea `choices[0].message.content` y `usage`. 4xx se consideran no reintentables; 429/5xx/timeouts/connection → reintento.
     - `MockLLMProvider`: devuelve JSON determinista (`{"task":..., "ok": true, ...}`); si `mock_failure` es True devuelve error simulado.
   - Fábrica `get_llm_provider(settings) -> BaseLLMProvider` según `settings.llm_provider`.

2. **Config `app/core/config.py`**
   - Añadir settings: `llm_provider: str = "mock"`, `llm_base_url: str`, `llm_api_key: str = ""`, `llm_model: str = "gpt-4o-mini"`, `llm_timeout_seconds: float = 15.0`, `llm_max_retries: int = 2`, `llm_retry_backoff: float = 0.5`, `llm_max_tokens: int = 1024`, `llm_rate_max_calls: int = 60`, `llm_rate_window_seconds: int = 60`.
   - `llm_api_key` como `SecretStr` (no se loggea).

3. **`app/core/rate_limit.py`**
   - `RateLimitStore` en memoria: `_calls: dict[key, list[timestamp]]` + lock; `is_allowed(key, max_calls, window_seconds)` y `record(key, now)`. Ventana deslizante simple (filtra por timestamp dentro de la ventana).

4. **`app/services/llm_orchestrator.py`**
   - `LLMOrchestrator` (instancia singleton con dependencias inyectables en tests).
   - `complete(*, task, system, user, model=None, temperature=0)`:
     1. Chequear `rate_limit.is_allowed(key=f"{tenant_id}:{user_id}")` → si no, `raise LLMRateLimitExceeded`.
     2. Llamar al provider con reintentos con backoff (max_retries): capturar `httpx.TimeoutException`, `httpx.ConnectError`, y códigos 429/5xx.
     3. Medir latencia; registrar métricas `llm_calls_total{task,status}`, `llm_latency_seconds{task}` (histograma), `llm_tokens_total{task}` con usage; audit log `llm.call` (service `llm`, detail con task/model/status/tokens/latency; sin prompt ni respuesta).
     4. Si fallan todos los reintentos → `LLMUnavailableError`.
   - Inyecta `AuditService` para auditoría.

5. **`app/api/routes_ai.py`**
   - `POST /v1/ai/ping` con `require_permissions(REQUEST_AI_SUGGESTION)`: invoca `orchestrator.complete(task="ping", system="Solo responde 'pong'.", user="ping")` y devuelve `{ok: true, model, latency_ms, task}`. Con mock devuelve 200 sin red.
   - `GET /v1/ai/info` con `require_permissions(VIEW_AUDIT)`: `{provider, model, rate_max_calls, rate_window_seconds}` — nunca api_key.
   - Registrar router en `main.py`.

6. **Tests `tests/test_llm.py`**:
   - Mock provider devuelve contenido esperado y usage > 0.
   - Rate limit: permitir `max_calls` y denegar el siguiente (usando ventana corta).
   - Orquestador con retry: mock de provider que falla 1 vez y luego ok → éxito y `llm_calls_total` status ok.
   - Timeout (mock que lanza `httpx.TimeoutException`) → `LLMUnavailableError` → endpoint 503.
   - `/v1/ai/ping` 401 (sin token) y 403 (rol agent sin REQUEST_AI_SUGGESTION si aplica — en el catálogo `agent` sí lo tiene; usar un rol sin permiso, verificar).
   - Métricas y auditoría registradas (`llm_calls_total` en `/v1/metrics`, evento `llm.call` en DB).
   - Suite completa sin regresión.

## Riesgos

- **Singleton con estado** — el orquestador y rate store deben resetearse entre tests (fixture).
- **Clave de rate limit por usuario/tenant** — se pasa explícitamente desde la ruta; el orquestador no sabe de tenants (decisión).
- **Formato OpenAI** — se asume; si el proveedor difiere, se ajusta en el provider concreto (el orquestador no se entera).
- **PII** — el orquestador recibe texto ya redactado; no guarda prompts; tests verifican que no queden prompts en auditoría ni métricas.