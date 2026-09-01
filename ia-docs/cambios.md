# Cambios

_Registro de cambios del proyecto. Formato: fecha · descripción · rama._

## 2026-09-01 · Paginación server-side en admin (usuarios y clientes)

- **`GET /admin/users`** → `UserListOut {items, total, limit, offset}`; nuevos filtros `q` (nombre o email `ilike`) y `role`. Se excluye `customer`.
- **`GET /admin/customers`** → `CustomerListOut {items, total, limit, offset}`; filtro `q` (nombre o empresa `ilike`) además de `tenant_id` validado por membresía.
- Renombrados `CustomerAdminOut` (item) y `CustomerListOut` (envelope); ajustados tests existentes (`test_users_name`, `test_permissions`, `test_tenant_isolation`) a `["items"]`. Suite backend **322 passed** (nota: `test_crypto::test_tampered_ciphertext_fails` es flaky, pasa aislado).

## 2026-09-01 · Pestaña "Clientes" en administración (endpoint sin PII)

- **`GET /admin/customers`** (`app/api/routes_admin.py`, requieren `CONFIGURE_TENANT`): lista clientes del/los tenant(s) con **email enmascarado** (`mask_email` en `app/services/pii.py`: `juan@x.com` → `ju***@x.com`) y filtro tenant-scoped. Acepta `tenant_id` opcional validado contra las membresías del usuario (403 si no es miembro). No expone emails crudos (PII).
- **Frontend**: tab "Clientes" en `AdminNav`, página `/app/admin/customers`, vista `AdminCustomersView` (nombre, email enmascarado, empresa, plan, registro) vía BFF `/api/bff/admin/customers` + hook `useAdminCustomers`.
- **Tests**: `tests/test_admin.py` +3 (listado enmascarado, aislamiento por tenant, 403 para agent). Suite backend **322 passed**.

## 2026-09-01 · Excluir clientes de la gestión de usuarios del admin

- **`GET /admin/users`** (`app/api/routes_admin.py`): el listado ahora filtra `User.role != "customer"`. Los clientes se auto-registran por el portal de personas (feature 020) y no se gestionan desde la consola de administración (no admiten cambio de rol ni gestión admin). Test manual como `demo.admin@example.com`.

## 2026-08-31 · Nombre de usuario y reglas de asignación — feature 018

- **Modelo**: `users.name` (`VARCHAR(255)`, nullable) en `app/models/user.py`; migración idempotente `scripts/migrate_users_name.py` (ALTER + backfill desde el local-part del email).
- **Schemas**: `RegisterRequest.name` (obligatorio), `UserOut.name`, `UserCreate.name` (obligatorio), `UserUpdate.name` (opcional; validator acepta name/role/is_active).
- **Registro** (`routes_auth.py`): persiste `name`; en rol `customer`, `customers.name` usa el nombre provisto (fallback al derivado del email).
- **Admin** (`services/admin.py` + `routes_admin.py`): `create_user`/`update_user` reciben y auditan `name`.
- **`GET /v1/agents`** (`routes_agents.py`, requiere `tickets:read`): agentes activos de los tenants efectivos (`AgentOut`: id/name/email/role), por membresía `user_tenants` o `users.tenant_id` legacy.
- **Reglas de asignación** en `PATCH /v1/tickets/{id}` (`routes_tickets.py`): `agent` solo puede asignarse a sí mismo o desasignar (403 si otro); `supervisor`/`tenant_admin`/`platform_admin` pueden asignar a cualquier **agente activo del tenant del ticket** (membresía o legacy; 404 si no). Auditoría incluye `assignee_name`.
- **Enriquecimiento**: `TicketOut`/`TicketSummaryOut.assignee {id,name,email,role}` y `TicketMessageOut.author_name` (`repositories/tickets.py` con queries batch); `KbArticleOut`/`KbArticleSummaryOut.author_name` (`repositories/kb.py`).
- **Seed demo**: `scripts/seed_demo_users.py` asigna nombres a los usuarios demo.
- **Tests**: `tests/test_users_name.py` (registro 201/422, me, admin CRUD con nombre) y `tests/test_assignments.py` (autoasignación, 403 a otro, supervisor→agente del tenant, 404 cross-tenant/inexistente, `/v1/agents`). Suite backend: **319 passed**. — `feat/bff`

## 2026-08-31 · Endpoints de tags (buscar y crear) — feature 017

- **`app/api/routes_tags.py`** (nuevo router `tags`, prefijo `/v1/tags`):
  - **`GET /v1/tags?search=`** — lista/busca tags del tenant por subcadena (`Tag.name.ilike("%search%")`, orden asc, tope 20). Requiere `tickets:read`.
  - **`POST /v1/tags`** con `TagCreate` — crea una tag para el tenant efectivo del usuario; valida nombre no vacío, evita duplicados por tenant (409) y registra auditoría (`tag.created`). Requiere `responses:edit`.
- **Registro**: router registrado en `app/main.py`.
- **Tests**: suite backend **302 passed** (sin cambios de tests existentes).

## 2026-08-28 · Búsqueda por categorías y tags — feature 023

- **Repositorio** `app/repositories/tickets.py`: `list()` acepta `q` (búsqueda de texto) y filtra con `or_` sobre `Ticket.category.ilike("%q%")` y una subconsulta `EXISTS` que matchea `Tag.name.ilike("%q%")` vía `ticket_tags`. Se mantiene el paginado (`limit`/`offset`) y el `total` sobre el mismo conjunto filtrado.
- **Endpoints**: se agrega query param `q` (máx. 100) a `GET /v1/tickets` (`routes_tickets.py`), `GET /v1/workspace/my-tickets` (`routes_workspace.py`) y `GET /v1/me/tickets` (`routes_persona.py`).
- **Alcance del filtro**: busca por **categoría** y **nombre de tags** (ambos en claro). Quedan fuera por estar cifrados en reposo: asunto (`subject`) y descripción (`description`) — política PII (ADR sobre cifrado). También fuera de alcance: email/usuario.
- **Tests**: se agregaron casos en `tests/test_tickets.py` (por categoría, case-insensitive, por tag, sin resultados, coexistencia con filtros/paginación) y `tests/test_persona_portal.py` (por categoría y sin resultados en el portal del cliente). Suite backend: **302 passed**.

## 2026-08-18 · Seed de usuarios y tickets demo — feature 022

- **`scripts/seed_demo_users.py`** (nuevo): crea usuarios demo con credenciales conocidas para la presentación del producto y tickets de ejemplo por tenant.
- **Usuarios demo** (password común `demo-pass-123`):
  - `demo.agente@example.com` (agent) · `demo.supervisor@example.com` (supervisor) · `demo.admin@example.com` (tenant_admin) — cada uno con membresía (`user_tenants`) en **todos** los tenants existentes.
  - `demo.plataforma@example.com` (platform_admin) — sin tenant, a nivel plataforma.
  - `demo.cliente.<slug>@example.com` (customer) — uno por tenant, con su fila en `customers` (vinculada por `user_id`, mismo criterio que el registro de la feature 021).
- **Tickets demo por tenant**: 5 tickets por empresa creados vía `TicketRepository` (cifrado AES-GCM en `subject`/`description`), con estados/prioridades/categorías variadas, algunos vinculados al cliente demo (`customer_id`) y asignados al agente demo, algunos con mensajes. Prefijo `[Demo]` en el asunto para detección idempotente.
- **Idempotente**: re-ejecutar no duplica usuarios, membresías, customers ni tickets.
- **Verificado** contra FastAPI (puerto local): login 200 con todos los demo users (con y sin `tenant_id`); `GET /v1/me/tickets` del cliente demo devuelve sus tickets; `platform_admin` demo lista `GET /v1/tenants`; agente demo lista/detalla tickets y mensajes.
- **Suite backend: 295 passed** sin regresión. — `feat/init-landing`

## 2026-08-17 · README.md

- Se creó `README.md` (estaba vacío) con la descripción del proyecto, stack, estructura, requisitos, instalación, cómo correr en local, tests, comandos útiles, resumen de API y seguridad.

## 2026-08-14 · Eliminado el endpoint de dashboard

- Se eliminó `GET /v1/dashboard` (`app/api/routes_dashboard.py`, `app/schemas/dashboard.py`) y su registro en `app/main.py`.
- El frontend ya no usa dashboard: `/app` redirige a `/app/tickets`.
- Se quitaron los tests de dashboard de `tests/test_multi_tenant_scope.py`. Suite backend: **295 passed**.

## 2026-08-14 · Portal de personas (rol customer) — feature 021

- **Rol `customer`** (`app/models/user.py` + `app/core/permissions.py`): nuevo rol de usuario final, permiso `persona:tickets`, agregado a `PUBLIC_REGISTRATION_ROLES`.
- **Registro de cliente** (`app/api/routes_auth.py`): con rol `customer` se crea la fila en `customers` (name derivado del email, tenant del primer tenant seleccionado, `user_id`).
- **Migración**: `scripts/migrate_customers_user_id.py` agrega `customers.user_id` (FK users.id, unique, nullable).
- **Repositorio/schemas**: `TicketRepository.list` acepta filtro `customer_id`; `create` acepta `customer_id`; `TicketView`/`TicketSummaryView` y `TicketOut`/`TicketSummaryOut` exponen `customer_id`.
- **Endpoints `/v1/me`** (`app/api/routes_persona.py`, permiso `persona:tickets`):
  - `GET /v1/me` — perfil del cliente (id, name, email, company, tenant_id, tenant_name).
  - `GET /v1/me/tickets` — mis tickets (aislado por customer + scope de tenants, filtros status/category/priority, paginación).
  - `POST /v1/me/tickets` — crear ticket como cliente (setea customer_id).
  - `GET /v1/me/tickets/{id}` — detalle aislado (404 cross-customer/tenant).
  - `GET|POST /v1/me/tickets/{id}/messages` — thread y envío de mensaje manual (sin LLM).
- **Tests**: `tests/test_persona_portal.py` (registro customer + perfil, flujo crear/listar, aislamiento cross-customer y cross-tenant, mensajes, 422 en ticket cerrado). Suite completa: **293 passed**.

## 2026-08-14 · Scope efectivo en LLM, workspace, admin, auditoría, KB y customers

- **`app/core/deps.py`**: nueva dependency `get_effective_tenant_ids_optional` (devuelve `[]` en vez de 403) para rutas de administración donde `platform_admin` (sin tenant) opera a nivel plataforma.
- **Servicios LLM ticket-scoped** (`classifier.py`, `summarizer.py`, `reply_suggester.py`, `analyze.py`): aceptan `tenant_ids` (lista) y derivan el tenant efectivo **del ticket** (`ticket.tenant_id`) para `AISuggestion`, orquestador y auditoría. Soportan alcance de varios tenants (usuario que salteó la selección).
- **`routes_ai.py`**: `classify`, `summary`, `suggested-reply` y `analyze` usan `get_effective_tenant_ids`.
- **Workspace** (`routes_workspace.py` + `services/feedback.py`): `my-tickets`, `suggestions` y `feedback` usan el scope efectivo (`IN (tenant_ids)`); `FeedbackService` acepta `tenant_ids` y usa el tenant de la sugerencia.
- **KB** (`repositories/kb.py` + `routes_kb.py`): `KbRepository` soporta `tenant_ids`; `set_tags` crea tags en el tenant del artículo. Rutas usan scope efectivo; auditoría scoped al primer tenant del alcance.
- **Customers** (`routes_customers.py`): listado y detalle filtran por `IN (tenant_ids)`.
- **Auditoría** (`routes_audit.py`): `GET /audit/events` filtra por `IN (tenant_ids)`.
- **Administración** (`services/admin.py` + `routes_admin.py`): `AdminService` recibe `tenant_ids`; `_require_tenant` pide un tenant único (403 si hay varios o ninguno). `list_tenant_users` usa scope efectivo (403 sin tenant); crear/editar usuarios y políticas usan `get_effective_tenant_ids_optional` para no romper a `platform_admin` (a nivel plataforma).
- **PII** (`routes_pii.py`): auditoría usa el tenant activo del token.
- **Tests**: suite backend completa **285 passed** sin regresión.

## 2026-08-14 · Fix flujo multi-tenant (portal empresas) y dashboard

- **Migración de esquema** (`scripts/migrate_tickets_customer_id.py`, `scripts/migrate_kb_article_tags.py`):
  - `tickets.customer_id` (FK a customers.id) faltaba en bases existentes → todo `/v1/tickets` devolvía 500.
  - `tickets.language` era NOT NULL sin default (columna que el modelo ya no usa) → los INSERT fallaban. Se le dio default `'es'`.
  - `kb_article_tags.tag` (string legacy) → `tag_id` FK a `tags.id` (Feature 019) → todas las operaciones KB devolvían 500.
- **Alcance de tenant desde el JWT** (`app/core/deps.py`):
  - `get_effective_tenant_ids`: si el token trae `tenant_id` → se usa ese único tenant (validando membresía o tenant legacy); si no trae (el usuario salteó la selección) → **todos** los tenants del usuario (`user_tenants`, fallback `users.tenant_id`). 403 solo si no tiene ningún tenant.
  - `get_token_tenant_id`: devuelve el tenant activo del JWT sin fallar si es vacío.
- **Tickets multi-tenant** (`app/repositories/tickets.py` + `app/api/routes_tickets.py`): `TicketRepository` acepta `tenant_ids`; listado, detalle, mensajes y tags filtran por `IN (tenant_ids)`. `_repo` usa el scope efectivo en lugar de `users.tenant_id`.
- **Dashboard real** (`app/api/routes_dashboard.py` + `app/schemas/dashboard.py`): `GET /v1/dashboard` con KPIs SQL sobre el scope del usuario (asignados a mí, abiertos, sin asignar, SLA en riesgo con ventana fija de 48h).
- **Registro con varios tenants** (`app/schemas/auth.py` + `app/api/routes_auth.py`): `RegisterRequest.tenant_ids` crea múltiples membresías. Con un solo tenant se setea `users.tenant_id` (primary, "ingreso directo"); con varios no hay primary (al saltar la selección ve todos). Valida que los tenants existan.
- **`/auth/me` refleja el tenant activo**: `me` devuelve el `tenant_id` del JWT (no el campo legacy) vía `get_token_tenant_id`.
- **`POST /auth/clear-tenant`**: emite tokens sin tenant activo (vuelve a "todos los tenants").
- **`GET /v1/tenants/public`**: lista pública de tenants (id, name, slug) para el formulario de registro.
- **Tests**: `tests/test_multi_tenant_scope.py` (9 tests) cubre registro multi-tenant, scope de tickets por tenant activo/todos, dashboard y tenants públicos. Suite completa: **285 passed**. Conftest siembra los tenants usados por las suites (el registro valida existencia).

## 2026-08-14 · Multi-tenant real implementado

- **Modelo nuevo**: `UserTenant` (`app/models/user_tenant.py`) - Relación many-to-many entre usuarios y tenants con rol específico por tenant
- **Modelo actualizado**: `User` ahora incluye relación `tenant_memberships` con `UserTenant`
- **Schema nuevo**: `app/schemas/user_tenant.py` - UserTenantOut, UserTenantCreate, TenantInfo
- **Schema actualizado**: `app/schemas/auth.py` - UserOut ahora incluye lista de tenants, LoginRequest acepta tenant_id, nuevo SwitchTenantRequest
- **Repositorio nuevo**: `app/repositories/user_tenant.py` - UserTenantRepository con métodos para gestionar membresías
- **Endpoints nuevos en auth**:
  - `POST /auth/switch-tenant`: Cambiar de tenant después del login
  - `GET /auth/tenants`: Listar tenants del usuario autenticado
- **Endpoints actualizados**:
  - `POST /auth/login`: Ahora acepta `tenant_id` opcional para seleccionar tenant al login
  - `GET /auth/me`: Ahora devuelve lista de tenants del usuario con sus roles
  - `POST /auth/register`: Crea automáticamente entrada en `user_tenants` si se especifica tenant_id
- **Migración de datos**: Script `scripts/migrate_user_tenants.py` migró 190 usuarios existentes a `user_tenants`
- **Tokens JWT**: Ahora incluyen tenant_id y role específicos del tenant seleccionado
- **Tests**: 276 tests pasan (sin regresiones)
- **Compatibilidad**: Se mantiene `users.tenant_id` por compatibilidad (se eliminará en futura migración)

## 2026-08-14 · Feature 020: Rediseño del detalle de ticket (Backend)

- Implementación de nuevos modelos y endpoints para soportar el rediseño del detalle de ticket.
- **Modelos nuevos**:
  - `Tenant` (`app/models/tenant.py`): id, name, slug, created_at
  - `Customer` (`app/models/customer.py`): id, tenant_id FK, name, email, company, plan, created_at
  - `Tag` (`app/models/tag.py`): id, tenant_id FK, name, created_at
  - `TicketTag` (`app/models/tag.py`): ticket_id FK, tag_id FK (many-to-many)
  - `KbArticleTag` actualizado para usar FK a Tag (antes string)
  - `Ticket` actualizado con FK `customer_id` (nullable) y relación `tags`
- **Schemas nuevos**:
  - `app/schemas/tenant.py`: TenantOut, TenantCreate
  - `app/schemas/customer.py`: CustomerOut, CustomerCreate, CustomerUpdate
  - `app/schemas/tag.py`: TagOut, TicketTagOut
  - `app/schemas/analyze.py`: AnalyzeOut, KbRecommendation, PiiDetection
- **Servicio nuevo**:
  - `app/services/analyze.py`: `AnalyzeService` que ejecuta classify, summary y suggested-reply en secuencia, más detección de PII y recomendaciones KB
- **Endpoints nuevos**:
  - `POST /v1/ai/tickets/{id}/analyze`: análisis unificado (classify + summary + reply + PII + KB recommendations)
  - `GET /v1/tickets/{id}/tags`: lista tags del ticket
  - `POST /v1/tickets/{id}/tags`: agrega tag al ticket
  - `DELETE /v1/tickets/{id}/tags/{tag_id}`: quita tag del ticket
  - `GET /v1/customers`: lista customers del tenant
  - `GET /v1/customers/{id}`: detalle de customer
  - `GET /v1/tenants`: lista tenants (requiere VIEW_AUDIT)
  - `GET /v1/tenants/{id}`: detalle de tenant
- **Seed**: `scripts/seed_tenants_customers.py` crea 2 tenants, 6 customers y 7 tags de prueba
- **Tests**: 16 tests nuevos (6 para /analyze, 10 para tags/customers/tenants)
- Suite backend: **276 tests pasados** (260 anteriores + 16 nuevos)
- Multi-tenant real (user_tenants) diferido para después de las tareas actuales
- Documentado en `ia_docs/features/020-rediseo-detalle-ticket/`

## 2026-08-14 · Feature 020: Rediseño del detalle de ticket (Backend) - COMPLETADA

**Estado final:** Feature completada parcialmente con multi-tenant diferido.

**Completado:**
- ✅ Modelos: Tenant, Customer, Tag, TicketTag, KbArticleTag actualizado
- ✅ Endpoints: /analyze, tags, customers, tenants
- ✅ Servicio AnalyzeService con ejecución en paralelo
- ✅ Seed de datos: 2 tenants, 6 customers, 7 tags
- ✅ Tests: 276 tests pasan (260 anteriores + 16 nuevos)
- ✅ Documentación actualizada

**Diferido para futura implementación:**
- ⏸️ Multi-tenant real con tabla user_tenants
- ⏸️ Migración de users.tenant_id a user_tenants
- ⏸️ Actualización del sistema de autenticación

**Nota:** El sistema actual mantiene la compatibilidad con users.tenant_id. La implementación de multi-tenant real se realizará en una feature futura.

---

## 2026-08-13 · Feature 019: Base de conocimiento (KB)

- Implementación completa de endpoints `/v1/kb/*` para gestionar artículos de base de conocimiento por tenant.
- **Permisos** (`app/core/permissions.py`): nuevos `KB_READ`, `KB_EDIT`, `KB_PUBLISH`. Agent solo lee; supervisor/tenant_admin/platform_admin pueden editar y publicar.
- **Modelos** (`app/models/kb.py`): `KbArticle` (artículo con title, body, category, status, tags, versionado), `KbArticleVersion` (snapshot por versión), `KbArticleTag` (tabla normalizada para tags).
- **Schemas** (`app/schemas/kb.py`): `KbArticleCreate`, `KbArticleUpdate`, `KbArticleOut`, `KbArticleSummaryOut`, `KbArticleListOut`, `KbArticleVersionOut`.
- **Repositorio** (`app/repositories/kb.py`): `KbRepository` con list (filtros status/category/tag/search), create, update (con versionado), publish/archive/restore (con validación de transiciones), list_versions.
- **Rutas** (`app/api/routes_kb.py`): 8 endpoints (listar, crear, detalle, actualizar, publicar, archivar, restaurar, versiones). Isolación por tenant (404 si artículo no existe o es de otro tenant). Auditoría de acciones sin PII.
- **Tests** (`tests/test_kb.py`): 23 tests (CRUD, permisos, isolación, versionado, transiciones, búsqueda, filtro por tag, auditoría).
- **Frontend** (`tests/knowledge.test.ts`): actualizado para validar flujo completo con backend real (11 tests nuevos).
- Suite backend: **259 tests pasados** (236 anteriores + 23 nuevos).
- Suite frontend: **106 tests pasados** (95 anteriores + 11 nuevos).
- Sin cifrado (los artículos no contienen PII).
- Documentado en `ia_docs/features/019-base-conocimiento/`.

## 2026-08-13 · Validación tenant_admin en suite funcional del frontend (Hallazgo 3)

- Se agregó `seedTenantAdmin()` en `tests/support/client.ts` para crear usuarios `tenant_admin` directamente contra FastAPI (vía `platform_admin`).
- Tests agregados en el frontend (`/home/kona/frontend-nextjs`):
  - `tests/admin.test.ts`: 6 tests nuevos para `tenant_admin` (listar usuarios del propio tenant, crear usuario en su tenant, crear en otro tenant → 403, crear platform_admin → 403, editar rol, editar usuario de otro tenant → 404).
  - `tests/audit.test.ts`: 2 tests nuevos para `tenant_admin` (leer eventos del propio tenant, filtrar por action).
  - `tests/ai-policy.test.ts`: 3 tests nuevos para `tenant_admin` (ai-info → 200, GET policy → 200, PUT round-trip idempotente, PUT modifica ai_enabled).
- Los tests usan tenants diferentes (`test-tenant-admin`, `test-tenant-audit`, `test-tenant-ai-policy`) para evitar interferencias.
- Suite frontend: **95 tests pasados** (83 anteriores + 12 nuevos, sin regresión).

## 2026-08-13 · Fix correlation id BFF→FastAPI (Hallazgo 5)

- El BFF del frontend ahora reenvía el `x-correlation-id` del cliente como `X-Request-ID` a FastAPI, y devuelve el trace del backend en el JSON de error.
- Cambios en el frontend (`/home/kona/frontend-nextjs`):
  - `src/lib/api/fastapi.ts`: acepta `correlationId` en opciones, lo envía como `X-Request-ID`, lee el header de respuesta del backend y lo incluye en `ApiError.correlationId`.
  - `src/lib/api/authenticated.ts`: lee `x-correlation-id` del request del cliente y lo pasa a `fastApiFetch`; `apiErrorResponse` incluye `correlation_id` en el JSON de error.
  - Route Handlers corregidos para pasar `req` a `authenticatedFetch` en GET: `tickets/route.ts`, `tickets/[ticketId]/route.ts`, `tickets/[ticketId]/messages/route.ts`, `knowledge/articles/route.ts`, `knowledge/articles/[articleId]/route.ts`, `knowledge/articles/[articleId]/versions/route.ts`, `admin/users/route.ts`, `admin/ai-policy/route.ts`, `admin/ai-policies/global/route.ts`, `admin/ai-info/route.ts`, `audit/events/route.ts`, `me/route.ts`.
- Tests:
  - `tests/hardening.test.ts`: nuevo test `correlation-id: el error del BFF incluye el trace del backend` que verifica que el `correlation_id` del backend se incluye en el JSON de error.
  - `tests/llm.test.ts`: actualizado para reflejar que el mock task-aware funciona (espera 200 en lugar de 422 en classify/summarize/suggest-reply/chat/stream).
- Suite frontend: **83 tests pasados** (sin regresión).

## 2026-08-13 · Fix mock LLM task-aware (Hallazgo 1)

- El `MockLLMProvider.complete` (`app/services/llm.py:141-179`) ahora es "task-aware": devuelve JSON válido según la tarea (`classify`, `summary`, `reply`), permitiendo que los parsers reales (`classifier.py`, `summarizer.py`, `reply_suggester.py`) acepten la salida en dev/tests sin inyectar mocks custom.
- `BaseLLMProvider.complete` y `HTTPLLMProvider.complete` aceptan el parámetro opcional `task: str | None = None` (los proveedores reales lo ignoran).
- `LLMOrchestrator._complete_with_retries` (`app/services/llm_orchestrator.py:200`) pasa `task=task` al proveedor.
- Tests de regresión:
  - `test_mock_provider_is_task_aware` (`tests/test_llm.py:43`): unit del mock por tarea.
  - `test_classify_success_with_default_mock` (`tests/test_classify.py:185`): E2E classify sin inyectar mock.
  - `test_summary_success_with_default_mock` (`tests/test_summary.py:108`): E2E summary sin inyectar mock.
  - `test_reply_success_with_default_mock` (`tests/test_reply.py:114`): E2E reply sin inyectar mock.
- Suite completa: **236 tests pasados** (sin regresión).

## 2026-08-13 · Fix consistencia total/items en listado de tickets (Hallazgo 4)

- `TicketRepository.list` (`app/repositories/tickets.py:166`) ejecutaba `count` y `select` en dos statements separados, lo que bajo escrituras concurrentes podía generar desfase entre `total` y `items` (observado 17 vs 18 en tests funcionales del frontend).
- Fix: query única con window function `COUNT(*) OVER()` para obtener `total` de la misma snapshot que los `items`, con fallback a `count` separado cuando `offset` supera el total (rows vacío).
- Tests agregados en `tests/test_tickets.py`:
  - `test_list_tickets_offset_beyond_total_returns_correct_count`: valida el fallback cuando offset > total.
  - `test_list_tickets_total_consistency`: valida que `total >= len(items)` y que el total refleje la cantidad real.
- Suite completa: **236 tests pasados** (229 originales + 2 nuevos + 5 de error handlers, sin regresión).

## 2026-08-11 · Mensajes de error automáticos de FastAPI en español

- FastAPI/Pydantic generan mensajes de error en inglés por defecto (validación 422, 404, 405, 500, etc.). Se agregaron handlers globales para que la API responda en español sin cambiar la estructura de la respuesta.
- `app/core/error_handlers.py` (nuevo) — `register_error_handlers()` con tres handlers:
  - `RequestValidationError` → 422 con `msg` traducido (ej. "Field required" → "Campo requerido", "String should have at least 8 characters" → "Debe tener al menos 8 caracteres", enum → "Debe ser '...' o '...'"); se conservan `loc`, `type` y `ctx`, y los mensajes de validadores custom ya en español se mantienen.
  - `HTTPException` → traduce solo los `detail` por defecto de Starlette ("Not Found" → "No encontrado", "Method Not Allowed" → "Método no permitido", etc.); los `detail` propios en español se devuelven intactos (ej. "Token inválido").
  - `Exception` → 500 genérico "Error interno del servidor" con log de la excepción.
- `app/main.py` — se registra `register_error_handlers(app)`.
- Tests: `tests/test_error_handlers.py` (nuevo, 5 casos). Suite completa **229 tests pasados**.
- Sin cambios en los mensajes propios (ya estaban en español).

## 2026-08-11 · Fix conexión al transaction pooler de Supabase

- La app no arrancaba con el `DATABASE_URL` del pooler de Supabase: la URL trae `?pgbouncer=true`, opción que psycopg2/libpq rechaza (`sqlalchemy.exc.ProgrammingError: invalid dsn: invalid connection option "pgbouncer"`). (Ya documentado para la nube en el entry del 2026-08-09, ahora resuelto en código.)
- `app/database.py` — nueva función `_build_database_url()` que sanitiza la URL antes de construir el engine: elimina las opciones de DSN `pgbouncer` y `connection_limit` (agregadas por el transaction pooler) cuando el driver es PostgreSQL. La nube ya usa el pooler de sesión, así que el fix no cambia su comportamiento.
- Verificado: `GET /health` → `{"status":"ok","version":"0.1.1"}`; suite completa **224 tests pasados**.
- **Release `v0.1.1`** — bumpeo `__version__` (0.1.0 → 0.1.1, patch) y deploy a FastAPI Cloud (`https://auto-help-desk.fastapicloud.dev`). — `main`

## 2026-08-09 · Despliegue a FastAPI Cloud

- Despliegue real en **FastAPI Cloud** (app `auto-help-desk`, URL `https://auto-help-desk.fastapicloud.dev`), cuenta `julieta.raw@gmail.com`.
- Preparación del repo para el despliegue:
  - `.python-version` — fija Python 3.12 para la nube (el CLI local usa 3.14).
  - `requirements.txt` — `fastapi==0.141.1` → `fastapi[standard]==0.141.1` (requisito de la plataforma).
  - `.fastapicloud/cloud.json` — vinculación del repo a la app (creada por el CLI).
- Variables de entorno de producción en la nube: `SECRET_KEY` (generada, secret), `DATABASE_URL` (Supabase, secret), `GEMINI_API_KEY` (secret), `LLM_PROVIDER=gemini`, `GEMINI_MODEL=gemini-3.6-flash`, `GEMINI_PROJECT_ID`.
- Bugs latentes de compatibilidad Python 3.12 encontrados en el deploy (el entorno local es 3.14 y PEP 649 difiere la evaluación de anotaciones, ocultándolos):
  - `app/api/routes_admin.py` — faltaba importar `TenantPolicy` (usado como anotación de retorno en `get_tenant_policy`/`save_tenant_policy`); agregado `from app.models.policy import TenantPolicy`.
  - `app/repositories/tickets.py` — `list[MessageView]` resolvía al método `list` de la clase en 3.12 (`'function' object is not subscriptable`); agregado `from __future__ import annotations`.
  - Validación completa: suite de 223 tests pasados dentro de un contenedor `python:3.12-slim` (docker) además del entorno local.
- `DATABASE_URL` — la URL del pooler de Supabase trae `?pgbouncer=true`, que psycopg2 rechaza (`invalid dsn`); en la nube se fijó el pooler de sesión (`:5432`, `?sslmode=require`, sin `pgbouncer`). Nota: el CLI de env no sobrescribe variables: hay que `env delete --yes` y luego `env set`.
- Verificación end-to-end contra el deploy: `GET /health` → `{"status":"ok","version":"0.1.0"}`; registro + login OK; `POST /v1/ai/ping` → `{"ok":true,"model":"gemini-3.6-flash"}` (Gemini real, no mock). Se creó un usuario de prueba (`e2e.deploy.<ts>@gmail.com`, id=1) en la DB de Supabase.
- Usuario admin para operación: `admin@autohelpdesk.app` / rol `platform_admin` (id=2, creado en la DB de Supabase). Las **credenciales viven en el `.env` local** (`ADMIN_EMAIL`/`ADMIN_PASSWORD`, gitignored), fuera del repo. Uso documentado en `ia_docs/operations/admin-users.md` (smoke test del LLM). Verificado en vivo: `GET /v1/ai/info` → `{"provider":"gemini","model":"gemini-3.6-flash",...}` y `GET /v1/metrics` con token de admin.
- Pendiente para próximos deploys: CORS (cuando exista frontend) y `OPENROUTER_API_KEY` (solo si se cambia `LLM_PROVIDER=openrouter`).
- **Seguridad — restricción de rol en el registro:** `/auth/register` ahora solo permite `agent` y `supervisor` (`PUBLIC_REGISTRATION_ROLES` en `app/api/routes_auth.py`); `platform_admin` y `tenant_admin` devuelven 403. El admin se provisiona por seed/DB o vía `/v1/admin/users`, nunca por auto-registro. Tests: `register_login` del conftest crea roles admin directo en DB; nuevo test `test_register_rejects_admin_roles`.

## 2026-08-09

- Soporte de proveedores LLM reales (`LLM_PROVIDER`): además de `mock` y `http` (genérico OpenAI-compatible), ahora `gemini` y `openrouter`. Sin SDKs: ambos usan el conector httpx OpenAI-compatible ya existente.
  - `app/core/config.py` — nuevas variables: `llm_chat_path` (ruta del chat completions, default `/v1/chat/completions`), `gemini_api_key`, `gemini_model`, `gemini_project_id`, `openrouter_api_key`; propiedad `llm_effective_model` (con `gemini` usa `GEMINI_MODEL` porque los nombres de Gemini no son compatibles con el default OpenAI).
  - `app/services/llm.py` — `HTTPLLMProvider` acepta `chat_path`; `get_llm_provider` resuelve `gemini` → `https://generativelanguage.googleapis.com` + `/v1beta/openai/chat/completions` (Google AI Studio), `openrouter` → `https://openrouter.ai/api` + `/v1/chat/completions`; fail-fast si falta la key o el provider es inválido.
  - Orquestador, `effective_global_policy` y `GET /v1/ai/info` usan `llm_effective_model` (el `GlobalPolicy.llm_model` sigue teniendo prioridad como override).
  - Pruebas reales (sin exponer keys): **Gemini OK** (`gemini-3.6-flash` → "pong", ~2s) y **OpenRouter OK** tras regenerar la key (el primer intento con la key anterior daba 401 "User not found" del lado del proveedor; la key nueva de 73 chars responde `openai/gpt-4o-mini` → "pong", ~1s).
  - `.env` — agregada `GEMINI_MODEL` (copiada del valor de `model`); `LLM_PROVIDER` se elige por entorno al arrancar (no se fija en `.env` para no desviar la suite de tests del mock).
  - Tests: `tests/test_llm.py` +7 (resolución de `llm_effective_model`, construcción de proveedores gemini/openrouter/http, key faltante → `ValueError`, provider inválido → `ValueError`, default mock).
  - Suite completa: **223 tests pasados** (baseline `216 passed` + 7 nuevos, sin regresión). — `develop`

## 2026-08-08

- Creación de la constitución del proyecto (`ia_docs/constitution/`): misión, roadmap y tech-stack, derivados de `spec.md` y `plan-ejecucion.md`. — `main`
- Commit inicial del repo con spec, constitución y plan de ejecución. — `main`
- Creación de ramas `develop` (integración) y `feature/fase-1` (trabajo de Fase 1).

### Fase 1 · Descubrimiento y diseño de arquitectura — rama `feature/fase-1`

- Feature 001 creada en `ia_docs/features/001-fase-1-descubrimiento/`.
- Creados los entregables de arquitectura en `ia_docs/architecture/`:
  - `00-indice.md` — índice y trazabilidad de entregables.
  - `00-casos-de-uso-roles-flujos.md` — catálogo de CU-01..CU-05, roles y flujos de tickets.
  - `01-matriz-requisitos.md` — matriz FR/RD/RS/RA/RNF/RG trazable al espec.
  - `02-arquitectura-multi-tenant.md` — diagrama y componentes cloud multi-tenant.
  - `03-modelo-datos-pii.md` — modelo de datos y diccionario con clasificación de PII.
  - `04-threat-model-seguridad.md` — amenazas y controles (JWT/OAuth, tenant, auditoría).
  - `05-politica-pii-retencion.md` — política de redacción, retención y minimización.
  - `06-estrategia-ia-guardrails.md` — prompts, grounding, guardrails y métricas.
  - `07-backlog-priorizado.md` — backlog derivado del plan de ejecución.
  - `ADR/ADR-000..005` — decisiones de arquitectura (aislamiento, orquestador LLM, modelo de datos, redacción PII, autenticación JWT).
- Actualizado `constitution/roadmap.md`: Fase 1 marcada como Hecho; siguiente es Fase 2.
- Merge de `feature/fase-1` en `develop` (commit `2bf4957`).

### Fase 2 · Fundamentos de Plataforma, Identidad y Seguridad — rama `feature/fase-2`

- AGENTS.md actualizado: nueva regla "No mergear a main/master sin pedir permiso".
- Feature 002 (Autenticación JWT/OAuth) creada en `ia_docs/features/002-autenticacion-jwt/`.
- Código base del backend FastAPI:
  - `app/core/config.py` — Settings vía pydantic-settings (clave secreta validada, mín. 32 chars).
  - `app/core/security.py` — hash argon2 (passlib) y JWT HS256 (PyJWT) con claims mínimos y errores diferenciados (expirado vs inválido).
  - `app/database.py` — engine, sesión y Base SQLAlchemy 2.x.
  - `app/models/user.py` — modelo `User` (email único, password_hash, role, tenant_id, active).
  - `app/models/token.py` — modelo `RefreshToken` (jti, expiración, revocación).
  - `app/schemas/auth.py` — schemas Pydantic v2 (register, login, refresh, logout, user, token).
  - `app/api/routes_auth.py` — endpoints `/auth/register|login|refresh|logout|me`.
  - `app/core/deps.py` — dependencia `get_current_user` (valida JWT y resuelve usuario).
  - `app/main.py` — app FastAPI con routers y `/health`.
- Tests en `tests/`: 11 pasados (register, login, refresh con rotación, logout/revocación, claims, 401 diferenciado).
- `.env.example` y `.env` actualizados con clave secreta larga.

### Fase 2 · Autorización por tenant y RBAC — rama `feature/003-rbac-tenant`

- Feature 003 creada en `ia_docs/features/003-rbac-tenant/`.
- `app/core/permissions.py` — catálogo de permisos por rol (spec §10.3) y dependencias `require_permissions` / `require_roles` (403 sin permiso).
- `app/core/deps.py` — nueva dependencia `get_tenant_id` (lee tenant_id del token, nunca del cliente).
- `app/repositories/base.py` — `TenantScopedRepository` (filtro por tenant obligatorio, ADR-001).
- `app/api/routes_admin.py` — endpoint de ejemplo `/admin/users` (RBAC + filtro por tenant).
- `app/main.py` — router admin registrado.
- Tests: `tests/test_permissions.py` + `tests/test_tenant_isolation.py` (aislamiento multi-tenant).
- Suite completa: 20 tests pasados (incluye regresión de feature 002).

### Fase 2 · Cifrado, secretos y protección de datos — rama `feature/004-cifrado-secretos`

- Feature 004 creada en `ia_docs/features/004-cifrado-secretos/`.
- `app/core/crypto.py` — cifrado AES-GCM de campos con clave derivada por HKDF desde `SECRET_KEY`; formato versionado `cipher:<v>:<salt>:<nonce>:<ct>:<tag>` con detección de manipulación.
- `app/core/config.py` — propiedad `encryption_key` (derivada de `SECRET_KEY`, nunca persistida).
- `ia_docs/architecture/04-threat-model-seguridad.md` — sección 6: cifrado en reposo/tránsito y plan de gestión de secretos (Vault).
- Tests: `tests/test_crypto.py` (round-trip, unicode, tamper nonce/ct, clave incorrecta, versión, formato, interop GCM).
- Suite completa: 31 tests pasados (incluye regresión de features 002-003).

### Fase 2 · Auditoría, logging y trazabilidad — rama `feature/005-auditoria`

- Feature 005 creada en `ia_docs/features/005-auditoria/`.
- `app/models/audit.py` — modelo `AuditEvent` append-only con campos mínimos del spec §11.2 (timestamp UTC, tenant, user, acción, trace_id, resultado, confianza, detail sin PII).
- `app/services/audit.py` — `AuditService` con `log(...)` (solo insert; sin update/delete).
- `app/core/deps.py` — dependencia `get_trace_id` (uuid por request).
- `app/api/routes_auth.py` — eventos auditados: login ok/fallido, refresh ok/fallido, logout, register, acceso a `/auth/me`.
- `app/api/routes_audit.py` — `GET /audit/events` protegido (`VIEW_AUDIT`), filtrado por tenant y paginado.
- `app/schemas/audit.py` — schema de salida `AuditEventOut`.
- Tests: `tests/test_audit.py` (auditoría de auth, sin PII, aislamiento por tenant, permisos, append-only).
- Suite completa: 39 tests pasados (incluye regresión de features 002-004).
- Commit `14011a1` en `feature/005-auditoria`; merge a `develop` (commit `8d27183`).
- Commit `14011a1` en `feature/005-auditoria`; merge a `develop` (commit `8d27183`).

### Fase 3 · API core de tickets — rama `feature/006-tickets`

- Feature 006 creada en `ia_docs/features/006-tickets/`.
- `app/models/ticket.py` — modelos `Ticket` (subject/description cifrados, status, category, priority, language, assignee, timestamps) y `TicketMessage` (body cifrado, FK a ticket con ondelete CASCADE).
- `app/schemas/ticket.py` — schemas Pydantic v2 (`TicketCreate`, `TicketUpdate`, `TicketOut`, `TicketListOut`, `TicketMessageIn/Out`) con validación de status/prioridad.
- `app/repositories/tickets.py` — `TicketRepository` (filtro por tenant, cifrado AES-GCM al escribir, descifrado al leer) que devuelve `TicketView`/`MessageView` (dataclass espejo) para no mutar el ORM con texto plano.
- `app/api/routes_tickets.py` — `/v1/tickets`: `POST` (create), `GET /{id}`, `GET` (listado con filtros status/category/priority/assignee/fechas y paginación), `PATCH /{id}`, `POST /{id}/messages`, `GET /{id}/messages`, `POST /{id}/close`. RBAC aplicado; otro tenant → 404.
- Auditoría en escrituras (ticket.created/updated/message/closed) con `trace_id` y `detail.ticket_id`.
- `app/main.py` — router de tickets registrado.
- Tests: `tests/test_tickets.py` (14 tests: CRUD, mensajes, cierre, cifrado en reposo, aislamiento 404, auditoría).
- Suite completa: **53 tests pasados** (incluye regresión de features 002-005).
- Commit `497c5a1` en `feature/006-tickets`; merge a `develop` (commit `e5c723c`).

### Fase 3 · Redacción de PII — rama `feature/007-pii`

- Feature 007 creada en `ia_docs/features/007-pii/`.
- `app/services/pii.py` — `PIIRedactor`: detección no-solapada de tipos PII (email, teléfono, tarjeta con Luhn, DNI/NIE, passport, fecha nacimiento, IP, URL interna) y reemplazo por tokens `[[PII:TIPO:hash8]]` con salt por request; modos `off|detect|redact`; tarjeta con Luhn inválido no se redacta.
- `app/schemas/pii.py` — schemas `PIIRedactRequest`, `PIIRedactResponse`, `PIIReportOut` (sin valores en claro).
- `app/api/routes_pii.py` — `POST /v1/pii/redact` protegido con `REQUEST_AI_SUGGESTION`; audita `pii.redacted` sin texto original.
- `app/main.py` — router de PII registrado.
- Tests: `tests/test_pii.py` (15 tests: detección por tipo, múltiples ocurrencias, tokens sin fuga, modos, Luhn, auditoría sin PII, 401).
- Suite completa: **68 tests pasados** (incluye regresión de features 002-006).
- Commit `717258d` en `feature/007-pii`; merge a `develop` (commit `77fbd89`).

### Fase 3 · Optimización de consultas y rendimiento — rama `feature/008-rendimiento`

- Feature 008 creada en `ia_docs/features/008-rendimiento/`.
- `app/models/ticket.py` — índices compuestos `ix_tickets_tenant_status`, `ix_tickets_tenant_created`, `ix_tickets_tenant_priority`; `description` marcada como columna diferida (`deferred=True`). `TicketMessage`: índice `ix_messages_ticket_created` y `body` diferida.
- `app/models/audit.py` — índice compuesto `ix_audit_tenant_created`.
- `app/repositories/tickets.py` — nueva vista `TicketSummaryView` para listados que NO accede a la columna diferida (evita N+1); `list()` la usa.
- `app/schemas/ticket.py` — `TicketSummaryOut` (sin `description`); `TicketListOut.items` lo usa.
- `app/api/routes_tickets.py` — el listado devuelve el resumen; el detalle sigue con `description`.
- Tests: `tests/test_schema.py` (8 tests: índices en metadata y recreados, deferred de `description`/`body`, listado sin exposición de PII, detalle intacto, sin N+1).
- `tests/test_tickets.py` — ajustado el test de cifrado en reposo para leer dentro de la sesión (compatibilidad con deferred).
- Suite completa: **76 tests pasados** (incluye regresión de features 002-007).

### Fase 3 · Observabilidad del backend — rama `feature/009-observabilidad`

- Feature 009 creada en `ia_docs/features/009-observabilidad/`.
- `app/core/metrics.py` — `MetricsRegistry` en memoria (counter, gauge, histograma con buckets Prometheus) sin dependencias externas; serialización a formato de texto Prometheus (`render_prometheus()`); instancia global `metrics` con `reset()` para tests.
- `app/core/logging.py` — logger de aplicación con filtro de `trace_id` (ContextVar `trace_id_var`), idempotente; sin PII.
- `app/core/observability.py` — `MetricsMiddleware` (BaseHTTPMiddleware): `http_requests_total{method,route,status}`, `http_request_duration_seconds` (histograma), `http_errors_total{status}` (≥400), `http_exceptions_total`; header `X-Request-ID` con el `trace_id`.
- `app/api/routes_metrics.py` — `GET /v1/metrics` (text/plain, formato Prometheus) protegido con `VIEW_AUDIT` (permiso existente en el catálogo RBAC; no se añadió `VIEW_METRICS`).
- `app/api/routes_tickets.py` — métricas de negocio: `tickets_created_total` y `tickets_closed_total` con label `tenant_id`.
- `app/main.py` — middleware y router de métricas registrados.
- Tests: `tests/test_metrics.py` (9 tests: 401/403/200, contadores/histogramas con requests reales, errores 404, métricas de negocio create/close, no-PII, formato Prometheus, reset).
- Suite completa: **85 tests pasados** (incluye regresión de features 002-008).

### Fase 4 · Orquestador LLM y conectores de IA — rama `feature/010-orquestador-llm`

- Feature 010 creada en `ia_docs/features/010-orquestador-llm/`.
- `app/services/llm.py` — conectores: `LLMUsage`, `LLMResponse`, `LLMUnavailableError` (fallback seguro) y `LLMRateLimitExceeded`; `HTTPLLMProvider` (httpx, OpenAI Chat Completions, timeout) y `MockLLMProvider` (determinista, dev/tests sin red); fábrica `get_llm_provider` según env.
- `app/core/config.py` — settings LLM (`llm_provider`, `llm_base_url`, `llm_api_key` SecretStr, model, timeout, retries, backoff, max_tokens, rate limit por ventana).
- `app/core/rate_limit.py` — `RateLimitStore` en memoria (ventana deslizante, thread-safe; sin Redis en el stack).
- `app/services/llm_orchestrator.py` — `LLMOrchestrator.complete()`: rate limit `tenant_id:user_id`, reintentos con backoff ante timeout/connect/5xx, métricas (`llm_calls_total{task,status}`, `llm_latency_seconds`, `llm_tokens_total`) reutilizando 009, y auditoría `llm.call` (sin prompts ni respuestas).
- `app/api/routes_ai.py` — `POST /v1/ai/ping` (REQUEST_AI_SUGGESTION; 429 por rate limit, 503 si LLM caído) y `GET /v1/ai/info` (VIEW_AUDIT, config sin secretos).
- `app/schemas/llm.py` — `LLMPingInfo`.
- `app/main.py` — router de IA registrado.
- Tests: `tests/test_llm.py` (13 tests: mock determinista, rate limit, retry→éxito, unavailable tras reintentos, auditoría, ping 401/200, info 401/403/200, ping auditado en DB).
- Suite completa: **98 tests pasados** (incluye regresión de features 002-009).

### Fase 4 · Clasificación automática de tickets — rama `feature/011-clasificacion`

- Feature 011 creada en `ia_docs/features/011-clasificacion/`.
- `app/models/ai_suggestion.py` — modelo `AISuggestion` (`ai_suggestions`): tenant_id, ticket_id (FK CASCADE), type (`classification|summary|reply`), output JSON (sin PII), confidence, model, prompt_version, state (`draft|accepted|rejected`), timestamps; índice compuesto `(tenant_id, ticket_id)`. Base para features 012/013 y feedback 015.
- `app/core/config.py` — `ai_confidence_threshold` (0.6), catálogos `ai_classify_categories` y `ai_classify_intents`.
- `app/prompts/classification.py` — prompt versionado `1.0.0` con separación instrucciones/datos (guardrail §12.1) y builders `build_classify_system`/`build_classify_user_prompt`.
- `app/services/classifier.py` — `TicketClassifier.classify()`: redacta PII del contexto (asunto/descripción/historial con `PiiRedactor`), invoca orquestador (tarea `classify`), valida JSON estructurado (`ClassificationError` como fallback seguro), persiste `AISuggestion` draft, audita `ai.classified` sin PII y registra `ai_classifications_total`.
- `app/schemas/ai.py` — `ClassificationOut` (contrato §15.1 + suggestionId + traceId).
- `app/api/routes_ai.py` — `POST /v1/ai/tickets/{ticket_id}/classify` con `REQUEST_AI_SUGGESTION`; 404 otro tenant, 429 rate limit, 503 LLM caído, 422 JSON inválido.
- Tests: `tests/test_classify.py` (8 tests: éxito con mock, baja confianza→warnings, otro tenant→404, 401, 503, 422, persistencia sin PII, auditoría+métricas; inyección del proveedor vía monkeypatch).
- Suite completa: **106 tests pasados** (incluye regresión de features 002-010).

### Fase 4 · Resumen automático de tickets — rama `feature/012-resumen`

- Feature 012 creada en `ia_docs/features/012-resumen/`.
- `app/prompts/summary.py` — prompt versionado `1.0.0` con separación instrucciones/datos (guardrail §12.1) y builders `build_summary_system`/`build_summary_user_prompt`.
- `app/services/summarizer.py` — `TicketSummarizer.summarize()`: contexto redactado de PII (asunto/descripción/historial), orquestador (tarea `summary`), validación JSON (`SummaryError` como fallback), persistencia `AISuggestion(type='summary')` draft, auditoría `ai.summarized` sin PII y métrica `ai_summaries_total`.
- `app/schemas/ai.py` — `SummaryOut` (contrato §15.2 + suggestionId + traceId).
- `app/api/routes_ai.py` — `POST /v1/ai/tickets/{ticket_id}/summary` con `REQUEST_AI_SUGGESTION`; 404 otro tenant, 429, 503, 422.
- Tests: `tests/test_summary.py` (8 tests: éxito con mock, baja confianza→warnings, otro tenant→404, 401, 503, 422, persistencia sin PII, auditoría+métricas).
- Suite completa: **114 tests pasados** (incluye regresión de features 002-011).

### Fase 4 · Sugerencia de respuesta editable — rama `feature/013-sugerencia-respuesta`

- Feature 013 creada en `ia_docs/features/013-sugerencia-respuesta/`.
- `app/prompts/reply.py` — prompt versionado `1.0.0` con separación instrucciones/datos (guardrail §12.1) y reglas de grounding (FR-08): basar solo en el contexto del ticket, no inventar precios/políticas/plazos, declarar fuentes y `policyFlags`.
- `app/services/reply_suggester.py` — `TicketReplySuggester.suggest_reply()`: contexto redactado de PII (asunto/descripción/historial con `PiiRedactor`), orquestador (tarea `reply`), validación JSON (`ReplyError` como fallback seguro), persistencia `AISuggestion(type='reply')` draft, auditoría `ai.replied` sin PII y métrica `ai_replies_total`.
- `app/schemas/ai.py` — `SuggestedReplyOut` (spec §15.3 + suggestionId + traceId) y `SuggestedReplyRequest` (tone/language opcionales).
- `app/api/routes_ai.py` — `POST /v1/ai/tickets/{ticket_id}/suggested-reply` con `REQUEST_AI_SUGGESTION`; 404 otro tenant, 429 rate limit, 503 LLM caído, 422 JSON inválido.
- Tests: `tests/test_reply.py` (9 tests: éxito con mock, tone/language, otro tenant→404, 401, 503, 422, baja confianza→warnings, persistencia sin PII, auditoría+métricas).
- Suite completa: **123 tests pasados** (incluye regresión de features 002-012).

### Fase 4 · Guardrails de IA — rama `feature/014-guardrails-ia`

- Feature 014 creada en `ia_docs/features/014-guardrails-ia/`.
- `app/services/guardrails.py` — `Guardrails` con `check_output()` (filtra salida del LLM: PII CRÍTICA no tokenizada vía `PiiRedactor.detect` = eco de PII T3, y contenido prohibido como jailbreak/cambio de rol/exfiltración; §12.3) y `check_input()` (patrones de prompt injection en el contexto del ticket, informativo sin bloquear; §12.1). `OutputBlockedError` y `GuardrailReport`.
- `app/core/config.py` — settings `guardrails_enabled`, `guardrail_prohibited_patterns` y `guardrail_injection_patterns` (regex conservadoras).
- `app/services/llm_orchestrator.py` — `complete()` aplica `check_input` (alerta auditada `llm.call` status `alert`, no bloquea) y `check_output` (si bloquea → métrica `ai_guardrail_blocks_total{reason,task}`, auditoría `llm.call` status `blocked` sin contenido, excepción `OutputBlockedError`); `_audit_call` ahora registra `result=status` (success/failure/blocked/alert).
- `app/api/routes_ai.py` — `OutputBlockedError` mapeado a 422 "Contenido bloqueado por política de seguridad" (spec §13.4) en classify/summary/suggested-reply/ping.
- Tests: `tests/test_guardrails.py` (11 tests: unitarios check_output/check_input, bloqueo por PII/jailbreak en salida, salida limpia pasa, auditoría+métricas del bloqueo, alerta de entrada auditada sin bloquear, `guardrails_enabled=False`).
- Suite completa: **134 tests pasados** (incluye regresión de features 002-013).

### Fase 5 · Workspace de agente — rama `feat/15-workspace-agente`

- Feature 015 creada en `ia_docs/features/015-workspace-agente/`.
- `app/models/feedback.py` — modelo `Feedback` (`feedback`): `suggestion_id` FK único a `ai_suggestions` (ondelete CASCADE), `tenant_id`, `action` (accepted|edited|rejected|flagged), `reason`, `edited_content_hash`, timestamps; índice `(tenant_id, suggestion_id)`.
- `app/models/ai_suggestion.py` — `state` ampliado a `draft | accepted | edited | rejected | flagged` (FR-09).
- `app/schemas/ai.py` — `FeedbackIn` (suggestion_id, action Literal, reason?, edited_content_hash?), `FeedbackOut`, `SuggestionOut` (id, type, state, confidence, model, prompt_version, output, created_at).
- `app/services/feedback.py` — `FeedbackService.record()`: valida que la sugerencia sea del tenant (otro tenant → `PermissionError`), upsert de feedback por `suggestion_id`, actualiza `AISuggestion.state`, audita `ai.feedback` (sin reason ni PII) y métrica `ai_feedback_total{action}`.
- `app/api/routes_workspace.py` — router `v1`:
  - `POST /v1/ai/tickets/{ticket_id}/feedback` (`EDIT_RESPONSE`): 404 ticket/sugerencia de otro tenant o inexistente; 422 action inválido.
  - `GET /v1/ai/tickets/{ticket_id}/suggestions` (`READ_TICKETS`): lista sugerencias del ticket del tenant (sin PII).
  - `GET /v1/workspace/my-tickets` (`READ_TICKETS`): bandeja del agente (tickets asignados a él), paginado, `TicketSummaryView`.
- `app/main.py` — router workspace registrado.
- Tests: `tests/test_workspace.py` (10 tests: feedback por acción actualiza state, 404 otro tenant/sugerencia inexistente, 422 action, listado de sugerencias con aislamiento por tenant, bandeja solo mis tickets, auditoría `ai.feedback` y métrica `ai_feedback_total`, 401).
- Suite completa: **144 tests pasados** (incluye regresión de features 002-014).

### Fase 5 · Administración de tenants y auditoría — rama `feat/16-administracion-auditoria`

- Feature 016 creada en `ia_docs/features/016-administracion-auditoria/` (spec §4.3/§4.4, FR-06, §11).
- `app/models/policy.py` — `TenantPolicy` (`tenant_policies`): `tenant_id` único, `ai_enabled`, `tone`, `language`, `allowed_categories` (JSON), `escalation_rules` (JSON), timestamps. `GlobalPolicy` (`global_policies`): fila única (id=1) con overrides de modelo/umbral/guardrails/rate; nulos = default de `.env`. Registrados en `app/models/__init__.py`.
- `app/schemas/admin.py` — `UserCreate`, `UserUpdate` (al menos role o is_active), `TenantPolicyIn/Out`, `GlobalPolicyIn/Out`.
- `app/services/admin.py` — `AdminService`: `create_user` (tenant_admin solo su tenant y sin crear `platform_admin`; platform_admin en cualquier tenant con tenant_id obligatorio; 409 email duplicado; 422 sin tenant_id), `update_user` (404 inexistente/otro tenant, 403 auto-desactivación y rol fuera de alcance), `get/save_tenant_policy` (upsert por tenant, FR-06), `get/save_global_policy` (overrides), y `effective_global_policy` (overrides + defaults). Auditoría `admin.user_created/user_updated/tenant_policy_updated/global_policy_updated` sin PII.
- `app/api/routes_admin.py` — `POST /admin/users` (201), `PATCH /admin/users/{user_id}`, `GET /admin/users` con paginación (limit/offset), `GET/PUT /admin/ai-policy` (`CONFIGURE_TENANT`), `GET/PUT /admin/ai-policies/global` (`MANAGE_AI_POLICIES`).
- `app/api/routes_audit.py` — `GET /audit/events` con filtros opcionales (action, service, user_id, result, date_from, date_to) y evento `audit.view` registrado al leer (§11.1).
- Tests: `tests/test_admin.py` (27 tests: CRUD de usuarios con restricciones de rol/tenant y aislamiento, políticas por tenant con aislamiento, políticas globales solo platform_admin, filtros de auditoría, evento `audit.view`, auditoría de acciones admin sin PII).
- Suite completa: **171 tests pasados** (incluye regresión de features 002-015).

### Fase 6 · Pruebas y red teaming — rama `feat/17-pruebas-red-teaming`

- Feature 017 creada en `ia_docs/features/017-pruebas-red-teaming/` (épicas 6.1-6.4; verificación, sin cambios de código de producto).
- `tests/datasets/` — paquete de datasets de control:
  - `redteam.py` — `INJECTION_PAYLOADS`: 6 payloads de prompt injection cubriendo 5 efectos (rol_change, exfiltration, reveal_prompt, embedded_instructions, jailbreak) con `expected_effect` y `expect_blocked_output`.
  - `classification.py` — `CLASSIFICATION_CASES`: 7 tickets de control (categorías billing/technical/account/general/feedback/urgent/other, intenciones request/incident/question/complaint/other, prioridades low/medium/high/urgent) con salida esperada, y `MockClassifyProvider` (mock determinista por caso, FR-01).
- `tests/test_redteam.py` (épica 6.4, §12.1):
  - Parametrizado `test_injection_payloads_do_not_execute_or_leak`: la inyección en el ticket NO se ejecuta ni filtra PII, y queda auditada como `llm.call` con `result="alert"`.
  - Parametrizado `test_blocked_output_when_llm_cooperates`: si el LLM "coopera" devolviendo el contenido peligroso, los guardrails responden 422 "Contenido bloqueado por política de seguridad".
  - `test_classify_ticket_of_other_tenant_404` / `test_suggestions_of_other_tenant_404`: cruce de tenants en classify/suggestions.
  - `test_rate_limit_exceeded_429`: exceder `llm_rate_max_calls` → 429 y auditoría `result="rate_limited"`.
- `tests/test_ia_evaluation.py` (épica 6.4, §17.2):
  - Parametrizado `test_classification_matches_dataset` sobre `CLASSIFICATION_CASES`: schema válido y categoría/intención/prioridad coherentes (FR-01).
  - `test_low_confidence_warning`: confianza 0.3 → warning de revisión humana (FR-07).
  - `test_reply_without_sources_has_warning` y `test_no_hallucination_when_no_grounding`: respuesta sugerida sin fuentes no alucina y advierte (FR-08).
- `tests/test_performance.py` (épica 6.3, §16): fixture `query_counter` (evento `after_cursor_execute` en el engine).
  - `test_list_does_not_load_deferred_description`: el listado no expone `description` (columna diferida, feature 008).
  - `test_list_emits_bounded_queries`: número fijo/bajo de queries (sin N+1), independiente del tamaño de la página.
  - `test_pagination_respects_limits` y `test_total_count_with_filters`: `limit`/`offset`/`total` correctos con y sin filtros.
- Evaluación IA y red teaming usan mock provider (dataset listo para proveedor real en 018); rendimiento mide patrón de consultas, no latencia absoluta (inestable en CI). Reutiliza `register_login`/`clean_db` del conftest y el patrón de mock de `test_guardrails.py`.
- Suite completa: **200 tests pasados** (baseline `171 passed` + 29 nuevos, sin regresión).
- `roadmap.md`: 017 movida a Hecho; Fase 6 iniciada; siguiente es 018 (CI/CD y operación).

### Fase 6 · CI/CD y operación — rama `feat/18-cicd-operacion`

- Feature 018 creada en `ia_docs/features/018-cicd-operacion/` (épicas 6.5-6.6; despliegue y operación).
- Dependencias reproducibles: `requirements.txt` (11 runtime pinneadas) y `requirements-dev.txt` (`-r requirements.txt` + `pytest==9.1.1`); verificadas con instalación limpia en venv nuevo → suite en verde. Se añadió `psycopg2-binary==2.9.12` para soportar `DATABASE_URL` PostgreSQL en producción (tech-stack lo contempla).
- `app/core/config.py` — `ai_features_enabled: bool = True` (kill-switch de despliegue); `SettingsConfigDict(extra="ignore")` para tolerar variables extra del entorno (p. ej. `DIRECT_URL` que genera Supabase) sin romper el arranque.
- Versionado: `app/__init__.py` → `__version__ = "0.1.0"`; `app/main.py` → `GET /health` devuelve `{"status": "ok", "version": __version__}` (smoke de release).
- Kill-switch (018): dependencia `_ai_features_enabled` en `routes_ai.py` sobre ping/classify/summary/suggested-reply → 503 "IA deshabilitada" + auditoría `ai.disabled` + métrica `ai_disabled_total`; no afecta a tickets ni al resto de la API.
- Rollout por tenant (018): dependencia `_tenant_ai_enabled` que respeta `TenantPolicy.ai_enabled` (default True si no hay fila) → 403 "IA deshabilitada para este tenant" + auditoría `ai.tenant_disabled` + métrica `ai_tenant_disabled_total`. Solo los endpoints de generación IA; listado de sugerencias, feedback e info no se bloquean.
- `app/services/policy.py` — `PolicyResolver.effective_global()`: valores efectivos de `GlobalPolicy` (via `effective_global_policy` de `admin.py`); sin fila → `GlobalPolicy(id=1)` con defaults de `.env` (sin cambio de comportamiento).
- Overrides de `GlobalPolicy` aplicados en runtime:
  - `LLMOrchestrator` acepta `model` y `rate_max_calls` (None = `settings`).
  - `Guardrails` acepta `enabled` (None = `settings.guardrails_enabled`).
  - `TicketClassifier`/`TicketSummarizer`/`TicketReplySuggester` aceptan `confidence_threshold` (antes leían settings internamente).
  - `routes_ai.py` construye el orquestador y los servicios con los valores efectivos del resolver (`_orchestrator(audit, policy)`).
- CI/release:
  - `.github/workflows/ci.yml` — job `test` (instala deps, `check_secrets.sh`, `compileall`, `pytest -q`, smoke `/health` con TestClient) y job `release` (`workflow_dispatch`, `environment: production`, `release.sh --push`, solo rama `develop`); `python-version: "3.12"`.
  - `scripts/check_secrets.sh` — verifica que `.env` no esté versionado y greps de patrones de secretos en archivos versionados.
  - `scripts/release.sh` — valida la suite, lee `__version__`, crea tag `vX.Y.Z`; `--push` opcional. Ambos scripts ejecutados OK localmente.
- `tests/conftest.py` — `/tmp/opencode` se crea con `mkdir(parents=True, exist_ok=True)` (robusto en CI con HOME limpio).
- `tests/test_deploy.py` — 16 tests: `/health` con `version`; kill-switch 503 en los 4 endpoints IA (auditoría `ai.disabled` + métrica, restauración al volver a `True`); rollout por tenant 403 (auditoría `ai.tenant_disabled` + métrica, `/v1/ai/info` no bloqueado, default sin fila = habilitado); overrides de `GlobalPolicy` (resolver honra overrides y defaults, `llm_model` llega al ping, `llm_rate_max_calls=1` → 429, `Guardrails(enabled=False)` vence a `settings`).
- Operación: `ia_docs/operations/` — `dashboard.md` (inventario de métricas de la 009 + queries PromQL sugeridas por panel), `alerts.md` (9 reglas base: LLM caído/degradado, 5xx, excepciones, guardrails, rate limit, kill-switch, tenant disabled, PII) y `runbooks/{release,rollback,incidents}.md` (LLM caído, prompt injection, fuga de PII, rate limit).
- `AGENTS.md` — comandos dev/test definidos (instalar deps, uvicorn dev, pytest, compileall, check_secrets, release, health).
- Suite completa: **216 tests pasados** (baseline `200 passed` + 16 nuevos, sin regresión).
- `roadmap.md`: 018 movida a Hecho; Fase 6 completada; el roadmap de las fases 1-6 está completo (features 001-018).
- Nota de entorno: el `.env` local apunta a PostgreSQL (Supabase) y quedó fuera de control de versiones; `extra="ignore"` + `psycopg2-binary` permiten arrancar con esa configuración.