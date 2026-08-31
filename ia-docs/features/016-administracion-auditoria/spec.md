# 016 · Administración de tenants y auditoría

**Estado:** implementado

## Qué hace

Backend de administración (Fase 5, épica 5.4; sin UI en el MVP): la consola que consumen el admin de tenant (spec §4.3) y el admin de plataforma (§4.4) para gestionar usuarios, políticas IA y auditoría. Completa la Fase 5.

- **Gestión de usuarios por tenant (§4.3, §10.3 "Configurar tenant")**: el admin de tenant crea usuarios de su tenant, cambia su rol y los activa/desactiva. El admin de plataforma puede hacerlo en cualquier tenant y asignar el rol `platform_admin`. El endpoint `GET /admin/users` ya existe; se amplía con paginación y creación/actualización.
- **Políticas IA por tenant (FR-06)**: cada tenant configura activación de IA, tono de respuesta, idioma preferido, categorías permitidas y reglas de escalamiento. Se persisten en una tabla `TenantPolicy` (por `tenant_id`, sin modelo Tenant).
- **Políticas globales de IA (§4.4, permiso `MANAGE_AI_POLICIES`)**: el admin de plataforma configura el modelo, umbral de confianza, guardrails y rate limit globales, sobreescribiendo los valores por defecto de `.env`.
- **Vistas de auditoría (§4.3, §4.4, §11)**: `GET /audit/events` se amplía con filtros (action, service, user_id, result, rango de fechas) y se audita el propio acceso a auditoría (`audit.view`, §11.1 "Acceso a auditoría") y los cambios de configuración (§11.1 "Cambios de configuración del tenant").

## Por qué

El spec define a los roles admin como responsables de configurar su tenant (§4.3) y de supervisar auditoría y políticas globales (§4.4), y FR-06 exige configuración por tenant (IA on/off, tono, idioma, categorías, escalamiento). Hoy el backend solo lista usuarios (`GET /admin/users`) y lista auditoría sin filtros ni auditoría del acceso; no hay forma de gestionar usuarios ni políticas IA. Esta feature entrega el contrato backend de la consola admin y alimenta las vistas de auditoría requeridas.

## Criterios de aceptación

- [x] Modelo `app/models/policy.py` (`TenantPolicy`): `tenant_id` único, `ai_enabled` (bool, default True), `tone`, `language`, `allowed_categories` (JSON list), `escalation_rules` (JSON), `created_at`/`updated_at`.
- [x] `app/services/admin.py` — `AdminService`:
  - `create_user(email, password, role, tenant_id)`: valida rol permitido por el rol invocante (tenant_admin no crea `platform_admin` ni usuarios de otro tenant), hash de password, audita `admin.user_created`.
  - `update_user(user_id, role?, is_active?)`: restricciones de rol iguales, no auto-desactivación, audita `admin.user_updated`.
  - `get_tenant_policy() / save_tenant_policy(data)`: lee/upserta `TenantPolicy` del tenant, audita `admin.tenant_policy_updated`.
  - `get_global_policy() / save_global_policy(data)`: lee/escribe políticas globales (en memoria o tabla), solo `MANAGE_AI_POLICIES`, audita `admin.global_policy_updated`.
- [x] Rutas `app/api/routes_admin.py` (ampliar, prefix `/admin`):
  - `POST /admin/users` (`CONFIGURE_TENANT`): crea usuario del tenant (201), 409 email duplicado, 422 rol inválido, 403 fuera de alcance del rol.
  - `PATCH /admin/users/{user_id}` (`CONFIGURE_TENANT`): actualiza rol/is_active, 404 inexistente u otro tenant.
  - `GET /admin/users` ya existente: se le agrega paginación (`limit`/`offset`) y mantiene `CONFIGURE_TENANT`.
  - `GET /admin/ai-policy` / `PUT /admin/ai-policy` (`CONFIGURE_TENANT`): políticas IA del tenant.
  - `GET /admin/ai-policies/global` / `PUT /admin/ai-policies/global` (`MANAGE_AI_POLICIES`): políticas globales.
- [x] `app/api/routes_audit.py` (ampliar): filtros opcionales en `GET /audit/events` (`action`, `service`, `user_id`, `result`, `date_from`, `date_to`) con índice existente `ix_audit_tenant_created` y paginación; cada acceso a auditoría se audita con `audit.view`.
- [x] `app/main.py`: sin cambios de registro (los routers ya están); nuevos modelos registrados vía `app/models/__init__.py`.
- [x] Tests `tests/test_admin.py`: creación de usuario admin (rol, tenant correcto, 201/409/403/422), actualización de rol/activo (404 otro tenant, 403 auto-desactivación/admin de tenant creando platform_admin), políticas IA por tenant (upsert, aislamiento entre tenants, 403 sin permiso), políticas globales (solo platform_admin), auditoría con filtros (action/service/user_id/fecha/result) y evento `audit.view` registrado, suite completa sin regresión.
- [x] Docs actualizados.

## Fuera de alcance

- UI de la consola admin (frontend aparte; el backend expone los contratos).
- Modelo `Tenant` con CRUD completo (crear/eliminar tenants no aparece en spec §4).
- Gestión de roles/permisos dinámicos por tenant (RBAC estático por rol, §10.3, ya implementado).
- Base de conocimiento / RAG (backlog).
- Integración con Vault para rotación de claves (§10.4, backlog de operación).
