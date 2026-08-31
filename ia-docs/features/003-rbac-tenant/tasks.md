# 003 · Autorización por tenant y RBAC — Tareas

_Checklist accionable derivada del `plan.md`. Tareas pequeñas y concretas; marca `[x]` al completarlas._

- [x] Crear `app/core/permissions.py` con catálogo de permisos por rol (spec §10.3).
- [x] Crear dependencia `require_roles(*roles)` que devuelve 403 sin permiso.
- [x] Agregar `get_tenant_id` en `app/core/deps.py` (lee tenant_id del token).
- [x] Crear `app/repositories/base.py` con `TenantScopedRepository` (filtro obligatorio por tenant).
- [x] Crear endpoint de ejemplo `/admin/users` (RBAC + filtro por tenant).
- [x] Escribir tests de permisos (401 sin token, 403 rol insuficiente, 200 con rol válido).
- [x] Escribir tests de aislamiento multi-tenant (tenant A no ve datos de tenant B).
- [x] Verificar regresión de la feature 002 (suite completa).
- [x] Validar contra los criterios de aceptación de `spec.md`.
- [x] Actualizar `ia_docs/cambios.md`, `roadmap.md`, `tasks.md` y `spec.md`.
- [x] Ejecutar la suite completa y reportar resultados.