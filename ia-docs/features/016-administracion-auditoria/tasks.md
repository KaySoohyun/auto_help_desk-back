# 016 · Administración de tenants y auditoría — Tareas

_Checklist accionable derivada del `plan.md`._

- [x] Modelo `app/models/policy.py`: `TenantPolicy` (tenant_id único, ai_enabled, tone, language, allowed_categories JSON, escalation_rules JSON, timestamps) y registro en `app/models/__init__.py`.
- [x] Schemas `app/schemas/admin.py`: `UserCreate`, `UserUpdate`, `TenantPolicyIn/Out`, `GlobalPolicyIn/Out`.
- [x] `app/services/admin.py`: `AdminService` (`create_user`, `update_user`, `get/save_tenant_policy`, `get/save_global_policy`) con restricciones de rol, auditoría y hash de password.
- [x] `app/api/routes_admin.py`: `POST /admin/users`, `PATCH /admin/users/{user_id}`, paginación en `GET /admin/users`, `GET/PUT /admin/ai-policy`, `GET/PUT /admin/ai-policies/global`.
- [x] `app/api/routes_audit.py`: filtros en `GET /audit/events` (action, service, user_id, result, date_from, date_to) y evento `audit.view` al leer.
- [x] Tests `tests/test_admin.py`: CRUD usuarios con restricciones de rol y aislamiento, políticas por tenant con aislamiento, políticas globales solo platform_admin, filtros de auditoría y evento `audit.view`.
- [x] Ejecutar suite completa sin regresión (`171 passed`).
- [x] Actualizar `ia_docs/cambios.md`, `roadmap.md` y spec/plan/tasks.
- [x] Feature 016 movida a "Hecho" en `ia_docs/constitution/roadmap.md` (Fase 5 completada).

## Notas

- `GET /admin/users` y `GET /audit/events` ya existen; la feature los amplía, no los duplica.
- RBAC es estático por rol (§10.3, `app/core/permissions.py`); la feature no añade permisos dinámicos por tenant.
- La creación de usuarios no toca `/auth/register` (se mantiene abierto, decisión del equipo).
- Las políticas globales son overrides sobre los defaults de `.env`; no se persisten secrets.
