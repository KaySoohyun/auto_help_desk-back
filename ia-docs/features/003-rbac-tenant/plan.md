# 003 · Autorización por tenant y RBAC — Plan

_Cómo se implementa lo descrito en `spec.md`. Debe respetar la `constitution/`._

## Enfoque

Se extiende el backend FastAPI existente sin romper la feature 002. Se agregan dos piezas ortogonales:

1. **RBAC** — catálogo de permisos por rol + dependencia `require_roles`.
2. **Aislamiento por tenant** — repositorio central que filtra por `tenant_id` del token.

Nada se ejecuta "en paralelo": RBAC primero (independiente), luego el repositorio, luego el ejemplo de endpoint con aislamiento.

## Estructura de archivos

```
app/
  core/
    permissions.py   # catálogo de permisos por rol + require_roles
    deps.py          # (modificar) exponer current_user + get_tenant_id
  repositories/
    base.py          # TenantScopedRepository (filtro obligatorio por tenant)
  api/
    routes_auth.py   # (modificar) /users/me (si aplica), crear admin de tenant
    routes_admin.py  # endpoint de ejemplo: /admin/users (RBAC + filtro tenant)
tests/
  test_permissions.py  # tests RBAC
  test_tenant_isolation.py  # tests aislamiento
```

## Implementación

1. `app/core/permissions.py` — diccionario `ROLE_PERMISSIONS` (rol → lista de permisos del spec §10.3) y dependencia `require_roles(*roles)`.
2. Modificar `app/core/deps.py` — agregar `get_tenant_id` (lee `tenant_id` del token) y reutilizar `get_current_user`.
3. `app/repositories/base.py` — `TenantScopedRepository` con métodos `get`, `list`, `add` que filtran por `tenant_id` (query con `WHERE tenant_id = ...`).
4. Endpoint de ejemplo: `/admin/users` (listar usuarios de un tenant) con `require_roles("platform_admin", "tenant_admin")` y filtro por tenant del token.
5. Refactor mínimo de `/auth/register` si hace falta para respetar aislamiento (los usuarios no son datos de negocio por tenant en el MVP).
6. Tests en `tests/test_permissions.py` y `tests/test_tenant_isolation.py`.
7. Actualizar `ia_docs/cambios.md`, `roadmap.md`, `tasks.md` y `spec.md`.

## Decisiones

- **Permisos como lista plana por rol** — simple y trazable al spec §10.3; se descartó jerarquía de roles para no complicar el MVP.
- **`require_roles` como dependencia FastAPI** — se compone con `get_current_user`; limpio y testeable.
- **Filtro por tenant en repositorio, no en endpoints** — invariante ADR-001; los endpoints no pueden olvidarse de filtrar.
- **`tenant_id` del token siempre** — nunca del body/query (spec §10.2); evita spoofing.
- **Usuarios sin tenant** — `platform_admin` puede tener `tenant_id` nulo (es global); el repositorio solo exige filtro a tablas de negocio.

## Riesgos

- **Romper la feature 002** — mitigación: tests de regresión existentes siguen pasando.
- **Filtro por tenant olvidado en queries ad-hoc** — mitigación: repositorio central como única puerta de acceso a datos de negocio.
- **`tenant_id` nulo en platform_admin** — mitigación: roles globales se validan por permiso RBAC, no por tenant.
- **Falsos positivos en aislamiento** — mitigación: tests que crean 2 tenants y verifican no-acceso cruzado.