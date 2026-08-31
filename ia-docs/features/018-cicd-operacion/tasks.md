# 018 · CI/CD y operación — Tareas

_Checklist accionable derivada del `plan.md`._

- [x] `requirements.txt` — dependencias runtime pinneadas (sin dependencias nuevas).
- [x] `requirements-dev.txt` — `-r requirements.txt` + pytest pinneado.
- [x] Verificación: instalación limpia + `pytest -q` en verde.
- [x] `app/__init__.py` — `__version__ = "0.1.0"`.
- [x] `app/main.py` — `/health` incluye `version` (mantener `status`).
- [x] `app/core/config.py` — `ai_features_enabled: bool = True`.
- [x] Kill-switch env en `routes_ai.py` (ping, classify, summary, suggested-reply → 503 + auditoría `ai.disabled` + métrica).
- [x] Rollout por tenant: dependencia que respeta `TenantPolicy.ai_enabled` (403 + auditoría `ai.tenant_disabled` + métrica); listado/feedback no bloqueados.
- [x] `app/services/policy.py` — `PolicyResolver` con valores efectivos de `GlobalPolicy`.
- [x] `LLMOrchestrator` — overrides opcionales (model, rate_max_calls) manteniendo default.
- [x] `Guardrails` — acepta `enabled` (override de `settings.guardrails_enabled`).
- [x] Clasificador/resumidor/sugeridor — aceptan `confidence_threshold` override.
- [x] `routes_ai.py` — orquestador construido con los valores efectivos del resolver.
- [x] `.github/workflows/ci.yml` — job `test` (deps, pytest, compileall, check_secrets, smoke) + job `release` con gate de aprobación.
- [x] `scripts/check_secrets.sh` — greps de patrones de secretos en archivos versionados.
- [x] `scripts/release.sh` — valida suite, lee `__version__`, crea tag `vX.Y.Z`.
- [x] `ia_docs/operations/dashboard.md` — métricas de la 009 + queries sugeridas.
- [x] `ia_docs/operations/alerts.md` — reglas base (latencia LLM, errores, guardrails, rate limit, tenant disabled).
- [x] `ia_docs/operations/runbooks/` — release, rollback e incidentes (LLM caído, prompt injection, fuga de PII, rate limit).
- [x] `AGENTS.md` — comandos dev/test definidos.
- [x] `tests/test_deploy.py` — kill-switch 503, rollout por tenant 403, overrides globales, `/health` con version.
- [x] Ejecutar suite completa sin regresión (`200 passed` → `216 passed`).
- [x] Actualizar `ia_docs/cambios.md`, `roadmap.md` (018 a Hecho, Fase 6 completa) y spec/plan/tasks.

## Notas

- Los overrides y flags NO cambian el comportamiento por defecto (sin `GlobalPolicy` o `TenantPolicy` = estado actual).
- CI se valida manualmente (los pasos del pipeline se ejecutan en local); GitHub Actions no corre en el repo.
- No se despliega a entornos reales: se entrega pipeline, release script y runbooks.
- Reutiliza `register_login`/`clean_db` del conftest y el patrón de monkeypatch de `tests/test_redteam.py`.
