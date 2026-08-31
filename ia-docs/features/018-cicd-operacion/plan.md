# 018 · CI/CD y operación — Plan

_Cómo se implementa lo descrito en `spec.md`._

## Enfoque

Feature de despliegue y operación. Primero se deja el repo reproducible (requirements + versionado), luego el pipeline CI, y por último se conectan al runtime las políticas de rollout que ya existen (016) con tests de comportamiento. Todo lo que toca comportamiento de producto es mínimo y se valida con tests dedicados; las políticas por defecto no cambian el comportamiento actual (no rompen la suite de 200).

## Implementación

1. **Dependencias reproducibles**
   - `requirements.txt` — pin exacto de las dependencias runtime instaladas (fastapi, uvicorn, sqlalchemy, pydantic, pydantic-settings, passlib, argon2-cffi, cryptography, PyJWT, httpx, email-validator y transitivas estrictas de runtime).
   - `requirements-dev.txt` — `-r requirements.txt` + pytest (con su versión pinneada).
   - Verificación: entorno limpio (`pip install -r requirements-dev.txt`) + `pytest -q` en verde.

2. **Versionado y release**
   - `app/__init__.py` — `__version__ = "0.1.0"`.
   - `app/api/routes_*` no cambia; `app/main.py` — `/health` devuelve `{"status": "ok", "version": __version__}` (se mantiene el test existente en `test_auth.py`, se amplía con el campo version).
   - `scripts/release.sh` — valida `python -m pytest -q`, lee `__version__`, crea tag `v{version}` (annotated), lo lista como salida. Push del tag es opcional (flag).

3. **Kill-switch de despliegue** (env)
   - `app/core/config.py` — `ai_features_enabled: bool = True`.
   - Dependencia en `app/api/deps.py` o `routes_ai.py`: si `not settings.ai_features_enabled`, los endpoints de generación (ping, classify, summary, suggested-reply) responden 503 "IA deshabilitada"; se audita `ai.disabled` (sin PII) y se incrementa métrica `ai_disabled_total`.

4. **Rollout por tenant** (`TenantPolicy.ai_enabled`)
   - Dependencia en `routes_ai.py` que carga la política del tenant (`ai_enabled` default `True` si no hay fila, reutilizando el criterio de `admin.py`).
   - Si `ai_enabled=false`: 403 "IA deshabilitada para este tenant"; auditoría `ai.tenant_disabled` y métrica `ai_tenant_disabled_total`.
   - Alcance: solo endpoints de generación IA (ping, classify, summary, suggested-reply). El listado `GET .../suggestions` y el feedback humano `POST .../feedback` NO se bloquean.

5. **Feature flags globales** (`GlobalPolicy` → runtime)
   - Nuevo `app/services/policy.py` — `PolicyResolver`: carga `GlobalPolicy` (fila 1) + `effective_global_policy(...)` y devuelve los valores efectivos (model, confidence threshold, guardrails_enabled, rate_max_calls), con cache corta por request.
   - `LLMOrchestrator` — acepta overrides opcionales (model y rate_max_calls) sin cambiar el default; `Guardrails` — acepta `enabled` (hoy lee `settings.guardrails_enabled` en `check_input`/`check_output`).
   - Clasificador/resumidor/sugeridor — aceptan `confidence_threshold` override para el warning de revisión humana (hoy usan `settings.ai_confidence_threshold`).
   - `routes_ai.py` — construye el orquestador con los valores efectivos del resolver.
   - Default (sin `GlobalPolicy`): comportamiento idéntico al actual (efectivos = `settings`).

6. **Pipeline CI** (`.github/workflows/ci.yml`)
   - Job `test`: checkout, `pip install -r requirements-dev.txt`, `pytest -q`, `python -m compileall app tests`, `scripts/check_secrets.sh`, smoke `uvicorn`+`/health` (o TestClient).
   - Job `release`: `workflow_dispatch` con gate de aprobación (environment `production`); ejecuta `scripts/release.sh`.
   - `scripts/check_secrets.sh` — greps de patrones (api_key, secret_key, contraseña, token) en archivos versionados; falla si hay coincidencia (sin dependencia externa).

7. **Operación y runbooks** (épica 6.6)
   - `ia_docs/operations/dashboard.md` — métricas que expone `GET /v1/metrics` (009) y queries Prometheus sugeridas.
   - `ia_docs/operations/alerts.md` — reglas base: latencia LLM p95, errores/unavailable, bloqueos de guardrails, `rate_limited`, `tenant_disabled`.
   - `ia_docs/operations/runbooks/*.md` — release (con `release.sh`), rollback (revert + tag anterior), incidentes: LLM caído (503 + fallback manual), prompt injection (alertas `llm.call`), fuga de PII (revocación/rotación + auditoría), rate limit.
   - `AGENTS.md` — definir comandos dev (`uvicorn app.main:app --reload`), test (`pytest -q`), lint (pendiente; se usa `compileall` como chequeo mínimo hasta definir linter).

8. **Tests** (`tests/test_deploy.py`)
   - Kill-switch: `AI_FEATURES_ENABLED=false` (monkeypatch settings) → classify/summary/reply/ping 503 + auditoría `ai.disabled`; `true` → 200.
   - Tenant rollout: crear `TenantPolicy(ai_enabled=False)` → endpoints de generación 403 + auditoría `ai.tenant_disabled`; `True` → 200; listado/feedback no bloqueados.
   - Overrides globales: `GlobalPolicy(llm_model="otro", guardrails_enabled=False, ai_confidence_threshold=0.1, llm_rate_max_calls=1)` → el orquestador usa el modelo override, no bloquea salida peligrosa, la confianza baja no genera warning, y el rate limit usa el override.
   - Health/version: `/health` incluye `version`.
   - Suite completa sin regresión (200 + nuevos).

## Riesgos

- **Falsa señal por settings globales**: `settings` es singleton; los tests de flags/overrides usan `monkeypatch.setattr(settings, ...)` y deben restaurarse (fixture `autouse`).
- **Enforcement por tenant rompe tests existentes**: los tests de 011-015/017 no crean `TenantPolicy` → default `ai_enabled=True` → no se rompen. Validar en la suite completa.
- **Overrides globales cambian el contrato del orquestador**: el default (sin `GlobalPolicy`) debe ser idéntico a hoy; cubrir con un test de no-regresión del comportamiento actual.
- **CI no se ejecuta localmente**: GitHub Actions no corre en el repo local; se validan los pasos del pipeline manualmente (instalación limpia, tests, compileall, check_secrets, smoke).
- **Rate limit override**: `rate_limit_store` es global y las ventanas se miden con el límite efectivo; el test de override debe resetear el store.
