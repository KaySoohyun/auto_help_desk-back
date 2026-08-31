# 016 · Administración de tenants y auditoría — Plan

_Cómo se implementa lo descrito en `spec.md`._

## Enfoque

Ampliar el backend de administración que ya existe parcialmente (`routes_admin.py` con `GET /admin/users`, `routes_audit.py` con `GET /audit/events`). Se añade gestión de usuarios (crear/actualizar), políticas IA por tenant (FR-06) y globales, y filtros + auditoría del acceso a auditoría. Reutiliza `TenantScopedRepository` (ADR-001), `AuditService` y `hash_password`. No se toca el pipeline LLM ni el modelo Tenant (fuera de alcance).

## Implementación

1. **Modelo `app/models/policy.py`**:
   - `TenantPolicy`: `id` PK, `tenant_id` (String(64), unique, index), `ai_enabled` (Boolean, default True), `tone` (String(50), nullable), `language` (String(10), nullable), `allowed_categories` (JSON list), `escalation_rules` (JSON), `created_at`/`updated_at` (DateTime tz).
   - Registrarlo en `app/models/__init__.py`.

2. **`app/services/admin.py`** — `AdminService(db, current_user, audit)`:
   - `create_user(email, password, role, tenant_id) -> User`:
     1. Si el invocante es `tenant_admin` → `tenant_id` obligatorio = el suyo; no permite `platform_admin`.
     2. Si es `platform_admin` → puede asignar cualquier rol y tenant (o `tenant_id` libre).
     3. Email duplicado → `ConflictError`/409.
     4. Hash de password, `is_active=True`, commit, audita `admin.user_created` (detail sin password).
   - `update_user(user_id, role=None, is_active=None) -> User`:
     1. Carga con `TenantScopedRepository` (otro tenant → `PermissionError` → 404).
     2. Restricciones de rol como en create; no permitir auto-desactivarse (si `user_id == current_user.id` y `is_active is False` → 403).
     3. Commit, audita `admin.user_updated`.
   - `get_tenant_policy() -> TenantPolicy`: busca por tenant_id; si no existe, devuelve defaults (ai_enabled=True).
   - `save_tenant_policy(data) -> TenantPolicy`: upsert por tenant_id, audita `admin.tenant_policy_updated` (detail sin PII).
   - `get_global_policy() -> GlobalPolicyOut`: valores actuales (modelo, umbral, guardrails, rate) desde `settings` + overrides en tabla `GlobalPolicy`.
   - `save_global_policy(data) -> GlobalPolicyOut`: persiste overrides, audita `admin.global_policy_updated`.

   En lugar de excepciones custom, se lanza `HTTPException` desde el service (patrón de la feature 014/015: validar y auditar en un solo lugar).

3. **Schemas `app/schemas/admin.py`**:
   - `UserCreate`: `email: EmailStr`, `password: str` (min 8), `role: UserRole`, `tenant_id: str | None`.
   - `UserUpdate`: `role: UserRole | None`, `is_active: bool | None` (al menos uno requerido).
   - `TenantPolicyIn`: `ai_enabled: bool`, `tone: str | None`, `language: str | None`, `allowed_categories: list[str]`, `escalation_rules: dict`.
   - `TenantPolicyOut`: como `TenantPolicyIn` + `updated_at`.
   - `GlobalPolicyIn`: `llm_model: str | None`, `ai_confidence_threshold: float | None`, `guardrails_enabled: bool | None`, `llm_rate_max_calls: int | None`.
   - `GlobalPolicyOut`: valores efectivos.

4. **Rutas `app/api/routes_admin.py`** (ampliar):
   - `POST /admin/users` (201, `CONFIGURE_TENANT`).
   - `PATCH /admin/users/{user_id}` (`CONFIGURE_TENANT`).
   - `GET /admin/users` → agregar `limit`/`offset` (paginación, feature 008).
   - `GET /admin/ai-policy` (`CONFIGURE_TENANT`): requiere `tenant_id` en el usuario.
   - `PUT /admin/ai-policy` (`CONFIGURE_TENANT`).
   - `GET /admin/ai-policies/global` (`MANAGE_AI_POLICIES`).
   - `PUT /admin/ai-policies/global` (`MANAGE_AI_POLICIES`).

5. **Rutas `app/api/routes_audit.py`** (ampliar):
   - `GET /audit/events` con filtros opcionales: `action: str | None`, `service: str | None`, `user_id: int | None`, `result: str | None`, `date_from: datetime | None`, `date_to: datetime | None`.
   - Construir `select` condicional; ordenar `created_at desc`; paginación existente.
   - Al inicio del handler, `audit.log("audit.view", ...)` para registrar el acceso (§11.1).

6. **Tests `tests/test_admin.py`**:
   - Helpers `register_login` (conftest) y payloads.
   - Casos: crear usuario admin (rol correcto, tenant asignado, 201); email duplicado 409; rol inválido 422; tenant_admin intentando crear `platform_admin` → 403; actualizar rol/is_active de usuario del tenant; usuario de otro tenant → 404; auto-desactivación → 403; políticas IA por tenant (crear y actualizar, aislamiento entre tenants); políticas globales solo platform_admin (403 para tenant_admin); auditoría con cada filtro (action, service, user_id, result, rango de fechas); evento `audit.view` presente al leer auditoría.

## Riesgos

- **Aislamiento**: creación/actualización de usuarios y políticas siempre con `TenantScopedRepository` o guarda explícita por tenant; los tests cubren cruce entre tenants.
- **Escalada de privilegios**: tenant_admin no puede crear `platform_admin` ni tocar otro tenant; reglas validadas en el service (no en la ruta).
- **Auditoría sin PII**: `admin.user_created/updated`, `admin.tenant_policy_updated`, `admin.global_policy_updated` y `audit.view` registran solo metadatos (ids, rol, acción), nunca emails/passwords en detalle sensible.
- **Políticas globales**: se guardan como overrides; los defaults de `.env` siguen siendo la base si un campo no se define.
