# Roadmap

_Orden y estado de las features. Es la vista de "qué hay hecho, qué toca ahora y qué viene". Cada entrada apunta a su carpeta en `features/`. Las fases 1-6 referencian `ia_docs/plan-ejecucion.md`._

## Hecho ✅

23. **023 · Búsqueda por categorías y tags** — param `q` en `GET /v1/tickets`, `GET /v1/workspace/my-tickets` y `GET /v1/me/tickets` que filtra por `category.ilike` y tag (`Tag.name` vía subconsulta `EXISTS`), respetando paginado y `total`. Asunto/descripción quedan fuera por estar cifrados en reposo (política PII). Frontend (cliente y agente) envía `q` al backend con debounce y elimina el filtrado en cliente. `302 passed`.

22. **022 · Seed de usuarios y tickets demo** — `scripts/seed_demo_users.py`: usuarios demo por rol con credenciales conocidas (`demo.agente/supervisor/admin/plataforma@example.com`, password `demo-pass-123`) con membresías en todos los tenants, `platform_admin` sin tenant, y un cliente demo por tenant (`demo.cliente.<slug>@example.com`) con su perfil en `customers`; tickets de ejemplo por empresa (cifrados, estados variados, algunos del cliente y asignados al agente). Idempotente y verificado contra FastAPI. `295 passed`.

20. **020 · Portal de personas (rol customer)** — rol `customer` vinculado a tenant + permiso `persona:tickets`; registro público crea su perfil en `customers` (`customers.user_id`); endpoints `/v1/me` (perfil, mis tickets, crear, detalle, mensajes) con aislamiento por customer y tenant; sin LLM. `293 passed`.

19. **019 · Flujo multi-tenant (portal empresas)** — alcance de tenant desde el JWT (`get_effective_tenant_ids`): tenant activo o todos los del usuario si saltea la selección; aplicado a tickets, LLM, workspace, KB, customers, auditoría y administración; registro con varios tenants (`tenant_ids`); `POST /auth/clear-tenant`; `GET /v1/tenants/public`; `/auth/me` refleja el tenant activo del token; migraciones de esquema (`tickets.customer_id`, `tickets.language` default, `kb_article_tags.tag_id`). `295 passed`. _(El dashboard se eliminó: `/app` redirige a tickets.)_

18. **018 · CI/CD y operación** — dependencias reproducibles (`requirements*.txt` pinneados), pipeline CI (tests, `compileall`, chequeo de secretos, smoke `/health`, release con gate de aprobación), `__version__` en `/health` y `scripts/release.sh` (tag `vX.Y.Z`), rollout por tenants y feature flags conectados al runtime (`TenantPolicy.ai_enabled` → 403; `AI_FEATURES_ENABLED=false` → 503; overrides de `GlobalPolicy` aplicados al orquestador/guardrails/servicios IA), y operación (`ia_docs/operations/` con dashboard, alertas y runbooks). `216 passed` sin regresión.
17. **017 · Pruebas y red teaming** — suite de verificación (Fase 6, épicas 6.1-6.4): datasets de control (`tests/datasets/redteam.py`, `classification.py`), red teaming de prompt injection sobre los endpoints IA reales (sin fuga de PII, auditoría `alert`, bloqueo 422, cruce de tenants 404, rate limit 429), evaluación de IA con dataset de control (FR-01/07/08, sin alucinación) y patrón de consultas de listados sin `description` diferida ni N+1. `200 passed` sin regresión.
1. **001 · Fundamentos y arquitectura** — base del repo, configuración `.env`, ADRs y backlog priorizado (Fase 1). Entregables en `ia_docs/architecture/`.
2. **002 · Autenticación JWT/OAuth** — login, refresh rotativo, logout con revocación, validación de tokens (exp, iss, aud, roles) y hash argon2.
3. **003 · Autorización por tenant y RBAC** — catálogo de permisos por rol, `require_roles`/`require_permissions`, repositorio con filtro por tenant (ADR-001) y tests de aislamiento multi-tenant.
4. **004 · Cifrado, secretos y protección de datos** — cifrado AES-GCM de campos (formato versionado, anti-tamper), validación de `SECRET_KEY` y plan de secretos (Vault).
5. **005 · Auditoría, logging y trazabilidad** — modelo `AuditEvent` append-only, `AuditService`, eventos de auth auditados, endpoint `GET /audit/events` protegido y paginado.
6. **006 · API core de tickets** — creación, consulta, listado con filtros/paginación, actualización, mensajes y cierre, con cifrado en reposo de campos sensibles y aislamiento por tenant.
7. **007 · Redacción de PII** — motor de detección/redacción de datos sensibles (email, teléfono, tarjetas, DNIs, fechas, IPs, URLs internas) con tokens seguros, modos off/detect/redact y auditoría sin valores originales.
8. **008 · Optimización de consultas** — índices compuestos (tenant+status/created/priority, ticket+created, audit+created), campos diferidos para PII pesada (listados sin `description`/`body`) y paginación con límites.
9. **009 · Observabilidad del backend** — registro de métricas en memoria (contadores, gauge e histogramas), middleware de latencia/errores/excepciones con `trace_id`, `GET /v1/metrics` en formato texto Prometheus protegido con `VIEW_AUDIT`, y métricas de negocio de tickets por tenant (sin PII). Sin dependencias externas.
10. **010 · Orquestador LLM y conectores de IA** — punto único de llamadas LLM (ADR-002): proveedores HTTP (httpx, OpenAI-compatible) y mock, timeout/reintentos con backoff, rate limit en memoria por tenant+usuario, fallback seguro (`LLMUnavailableError`), métricas de tokens/latencia/errores (feature 009) y auditoría `llm.call` sin prompts. Expone `POST /v1/ai/ping` y `GET /v1/ai/info`.
11. **011 · Clasificación automática de tickets** — servicio `TicketClassifier` sobre el orquestador: contexto redactado de PII, prompt versionado, salida JSON validada (categoría, subcategoría, intención, prioridad, confianza, rationale, warnings), persistencia en `ai_suggestions` (draft) y umbral de confianza con advertencia de revisión humana. `POST /v1/ai/tickets/{id}/classify`.
12. **012 · Resumen automático de tickets** — `TicketSummarizer` con el mismo pipeline seguro: contexto redactado, tarea `summary`, resumen breve y accionable + información faltante, persistencia en `ai_suggestions` (draft) y umbral de confianza. `POST /v1/ai/tickets/{id}/summary`.
13. **013 · Sugerencia de respuesta editable** — `TicketReplySuggester` con el mismo pipeline seguro: contexto redactado, tarea `reply`, borrador editable con grounding y fuentes (FR-08), `policyFlags` para aspectos no verificables, persistencia en `ai_suggestions` (draft) y umbral de confianza. `POST /v1/ai/tickets/{id}/suggested-reply`.
14. **014 · Guardrails de IA** — capa de guardrails en el orquestador (ADR-002): filtro de salida (PII cruda + contenido prohibido/jailbreak) que bloquea y audita `ai_guardrail_blocks_total` con 422 "Contenido bloqueado por política de seguridad", y alerta de prompt injection en entrada (audita sin bloquear).
15. **015 · Workspace de agente** — feedback del agente sobre sugerencias IA (`POST /v1/ai/tickets/{id}/feedback` con accepted/edited/rejected/flagged que actualiza el estado de la `AISuggestion`), panel IA por ticket (`GET /v1/ai/tickets/{id}/suggestions`) y bandeja del agente (`GET /v1/workspace/my-tickets`). Regenerar/escalar reutilizan endpoints existentes.
16. **016 · Administración de tenants y auditoría** — gestión de usuarios por tenant (crear/actualizar rol/activo, paginación), políticas IA por tenant (`TenantPolicy`, FR-06), políticas globales de IA (overrides de `.env`, solo `MANAGE_AI_POLICIES`) y vistas de auditoría con filtros (action/service/user_id/result/fechas) que auditan el propio acceso (`audit.view`).

## Siguiente 🔜

_Bajo demanda. El roadmap de las fases 1-6 (features 001-018) está completo._

## Fase 3: Backend / Almacenamiento Cloud 💾

_Completada (features 006-009)._

## Fase 4: Integración API IA 🤖

_Completada (features 010-014)._

10. **010 · Orquestador LLM y conectores de IA** — gateway con timeouts, reintentos, fallback y límites de uso.
11. **011 · Clasificación automática de tickets** — categoría, subcategoría, intención y prioridad sugerida con confianza.
12. **012 · Resumen automático de tickets** — problema principal, acciones previas, estado actual e información faltante.
13. **013 · Sugerencia de respuesta editable** — borrador con grounding y fuentes.
14. **014 · Guardrails de IA** — prompt injection, control de alucinaciones, validación de salida y fallback seguro.

## Fase 5: Experiencia de Agente y Administración 🖥️

_Completada (features 015-016)._

15. **015 · Workspace de agente** — gestión de tickets, colas y panel de asistencia IA (aceptar/editar/rechazar/escalar).
16. **016 · Administración de tenants y auditoría** — usuarios, roles, permisos, políticas IA y vistas de auditoría.

## Fase 6: Testing / Despliegue 🚀

_Completada (features 017-018)._

17. **017 · Pruebas y red teaming** — funcionales, seguridad/privacidad multi-tenancy, rendimiento y evaluación de IA.
18. **018 · CI/CD y operación** — pipelines, rollout por tenants, feature flags, dashboards, runbooks y release a producción.

## Backlog / ideas 💡

_Sin comprometer ni ordenar del todo. Ideas que respetan la constitución._

- **Base de conocimiento por tenant (RAG avanzado)** — artículos aprobados con filtro por idioma y vigencia.
- **Métricas de calidad y uso** — precisión de clasificación, tasas de aceptación/rechazo y evaluación con dataset de control.
- **Detección proactiva de tickets duplicados** — sugerir próximos mejores acciones.
- **Analítica de calidad por agente y por equipo.**
- **Soporte multi-idioma completo.**

> Cada feature nueva se crea como `features/NNN-nombre-feature/` con `spec.md`, `plan.md` y `tasks.md` antes de tocar código.
