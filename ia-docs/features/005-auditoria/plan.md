# 005 · Auditoría, logging y trazabilidad — Plan

_Cómo se implementa lo descrito en `spec.md`. Debe respetar la `constitution/`._

## Enfoque

Se agrega un modelo `AuditEvent` append-only, un `AuditService` inyectable, y se engancha en los puntos clave de auth (`routes_auth.py`). Los endpoints de auditoría se protegen con RBAC (reuso de `require_permissions(VIEW_AUDIT)`). El `trace_id` se genera por request y se propaga en los eventos y en los logs operativos, sin loggear datos sensibles.

## Estructura de archivos

```
app/
  models/
    audit.py            # AuditEvent (append-only)
  services/
    audit.py            # AuditService.log(...)
  api/
    routes_auth.py      # (modificar) emitir eventos de login/logout/refresh/register
    routes_audit.py     # GET /audit/events (protegido, filtrado por tenant, paginado)
  core/
    deps.py             # (opcional) helper para trace_id por request
tests/
  test_audit.py         # tests de auditoría
```

## Implementación

1. `app/models/audit.py` — modelo `AuditEvent`: id, created_at (UTC), tenant_id, user_id, action, service, model, model_version, prompt_version, trace_id, result, confidence, detail (json, sin PII).
2. `app/services/audit.py` — `AuditService(db)` con `log(action, *, user, tenant_id, service, result, ...)`; siempre inserta; nunca ofrece update/delete. Fecha UTC.
3. Modificar `app/models/__init__.py` para importar el nuevo modelo (creación de tablas en startup).
4. En `app/api/routes_auth.py`:
   - login exitoso → `auth.login_success`; login fallido → `auth.login_failed` (con email sin PII? sí, es un id, se permite).
   - logout → `auth.logout`.
   - refresh → `auth.refresh`.
   - register → `auth.user_registered`.
5. `app/api/routes_audit.py` — `GET /audit/events` con `require_permissions(VIEW_AUDIT)`, filtro por tenant (repositorio o query con tenant_id del usuario), paginación (limit/offset) y orden descendente por created_at.
6. Middleware/dependency `get_trace_id`: uuid4 por request, pasado a AuditService; también se loggea en logs operativos sin PII.
7. Tests:
   - login ok registra evento con trace_id.
   - login fallido registra evento.
   - append-only: no hay endpoint de borrado; intento de `db.delete` no disponible vía servicio.
   - consulta de auditoría: tenant A no ve eventos de tenant B; requiere rol con VIEW_AUDIT.
   - paginación funciona.
   - el evento no contiene password ni contenido sensible.
8. Actualizar `ia_docs/cambios.md`, `roadmap.md`, spec/tasks.

## Decisiones

- **Append-only por diseño**: el servicio expone solo `log()`, sin métodos de update/delete; la tabla se marca como tal en docs. Cumple §11.3 (inmutabilidad de auditoría).
- **`AuditService` inyectable por dependencia** — se inyecta en routers; fácil de testear con DB de test.
- **`detail` como JSON sin PII** — captura contexto no sensible (p. ej. resultado, confianza) sin almacenar contraseñas ni contenido de tickets.
- **`trace_id` por request** — generado en la dependencia y compartido con logs operativos para correlación (§11.2).
- **Roles**: `VIEW_AUDIT` (supervisor, tenant_admin, platform_admin) — reuso del catálogo existente.
- **No loggear payloads**: en login fallido solo se registra el email (identificador), nunca la contraseña.

## Riesgos

- **Registrar datos sensibles por error** — mitigación: test explícito de que no hay PII; `detail` con schema controlado.
- **Auditoría que crece sin límite** — mitigación: fuera de alcance la purga (retención en Fase 3), pero se documenta.
- **Olvidar eventos en un flujo** — mitigación: punto único `AuditService` + tests sobre los flujos de auth.
- **Rendimiento de la escritura de auditoría** — mitigación: insert simple, sin joins en el write path; paginado en lectura.