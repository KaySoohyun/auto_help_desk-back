# 018 · CI/CD y operación

**Estado:** implementado

## Qué hace

Última feature de Fase 6 (épicas 6.5-6.6). Convierte el repo en desplegable con control: dependencias reproducibles, pipeline CI con controles de calidad y seguridad, paquete de release con versionado, rollout por tenants y feature flags (kill-switch) que conectan las políticas ya existentes (`TenantPolicy.ai_enabled`, `GlobalPolicy`) al runtime de los endpoints IA, y documentación de operación (dashboard, alertas, runbooks). No añade funcionalidad de producto nueva; añade la capa de despliegue y operación.

- **Dependencias reproducibles**: `requirements.txt` (runtime) y `requirements-dev.txt` (pytest), con versiones pinneadas de lo ya instalado. No se inventan dependencias.
- **Pipeline CI** (`.github/workflows/ci.yml`): instala deps, corre la suite completa (`pytest`), chequeo de sintaxis (`compileall`), chequeo de secretos hardcodeados, y smoke de `/health`. Job de release manual con gate de aprobación (crea tag semver).
- **Paquete de release**: `__version__` en `app/__init__.py` expuesta en `/health`; `scripts/release.sh` valida la suite y crea el tag `vX.Y.Z`.
- **Rollout por tenants y feature flags** (épica 6.5):
  - Kill-switch de despliegue por env `AI_FEATURES_ENABLED` (default `true`): si `false`, los endpoints IA responden 503 "IA deshabilitada" (fallback controlado, no rompe la gestión de tickets).
  - Rollout por tenant: enforcement de `TenantPolicy.ai_enabled` en los endpoints de generación IA (classify, summary, suggested-reply, ping): si `false` → 403 "IA deshabilitada para este tenant", auditado y medido.
  - Feature flags globales: aplicar los overrides de `GlobalPolicy` (llm_model, ai_confidence_threshold, guardrails_enabled, llm_rate_max_calls) en runtime, conectando la política global de la 016 con el orquestador LLM.
- **Monitoreo y alertas** (épica 6.6): documentación del dashboard base (métricas Prometheus de la 009, queries sugeridas) y reglas de alerta (latencia LLM, errores, bloqueos de guardrails, rate limit, aislamiento de tenant).
- **Runbooks y operación** (épica 6.6): `ia_docs/operations/` con runbooks de release/rollback e incidentes (LLM caído, prompt injection, fuga de PII, rate limit), y `AGENTS.md` con los comandos dev/test definidos (TODO pendiente).

## Por qué

- La 016 creó `TenantPolicy.ai_enabled` y `GlobalPolicy` con UI de administración, pero **no se aplican en runtime**: un tenant con IA deshabilitada puede seguir llamando a los endpoints IA, y los overrides globales no llegan al orquestador. Esa brecha de "rollout por tenants y feature flags" que pide el roadmap es la que cierra la 018.
- El plan de ejecución (épicas 6.5-6.6) exige pipelines con controles de calidad/seguridad y aprobación, estrategia de rollout por tenants con feature flags y rollback, dashboards, runbooks y paquete de release.
- Hasta ahora no hay `requirements*.txt`, CI ni versionado: el repo solo es reproducible con el `.venv` local.

## Criterios de aceptación

- [ ] `requirements.txt` y `requirements-dev.txt` pinneados reproducen el entorno (instalación limpia + suite completa en verde).
- [ ] `.github/workflows/ci.yml`: tests, `compileall`, chequeo de secretos y smoke `/health`; job de release manual que crea tag `vX.Y.Z`.
- [ ] `/health` responde `{"status": "ok", "version": "<__version__>"}` (smoke de release).
- [ ] `scripts/release.sh` valida la suite completa y crea el tag semver.
- [ ] `AI_FEATURES_ENABLED=false` → endpoints de generación IA devuelven 503 (auditado + métrica); `true` → funcionan.
- [ ] `TenantPolicy.ai_enabled=false` → endpoints de generación IA devuelven 403 (auditado + métrica); `true` → funcionan. El listado de sugerencias y el feedback humano no se bloquean.
- [ ] Overrides de `GlobalPolicy` aplicados en runtime: `llm_model`, `guardrails_enabled`, `ai_confidence_threshold`, `llm_rate_max_calls` (tests con DB).
- [ ] `ia_docs/operations/`: `dashboard.md`, `alerts.md`, runbooks de release/rollback e incidentes; `AGENTS.md` con comandos definidos.
- [ ] Suite completa sin regresión (`200 passed` → incremento).

## Fuera de alcance

- Infraestructura cloud real (landing zone, EKS/ECS, redes): requiere cuenta y acceso; se documenta como actividad en runbooks.
- Containerización (Dockerfile/registry): no está en el stack; se documenta como opción de operación futura.
- Deploy a entornos reales de staging/producción: se entrega el pipeline y el runbook, no el despliegue (no hay acceso).
- Pentesting externo y plan de remediación formal.
- Monitoreo de infraestructura (APM, logs en cloud): se documenta el dashboard de aplicación que ya expone la 009.
