# 005 · Auditoría, logging y trazabilidad

**Estado:** implementado ✅

## Qué hace

Capa de auditoría de la plataforma (Fase 2, épica 2.5 del plan de ejecución). Registra de forma inmutable y trazable los eventos de seguridad y operación definidos en el spec §11:

- **Eventos de acceso**: login, logout, refresh, acceso a recursos protegidos.
- **Acciones de agentes y administración**: creación de usuarios, cambios de configuración.
- **Base para actividad de IA** (feature 004/005 del roadmap): la estructura de auditoría queda lista para los eventos IA de Fase 4.
- **Datos mínimos por evento** (§11.2): timestamp UTC, tenant_id, user_id o service, acción, modelo/versión si aplica, trace_id, resultado.
- **Separación**: tabla de auditoría `append-only` (nunca UPDATE/DELETE) y logging operativo por separado (§11.3).

## Por qué

Es requisito del spec (§11, RA-01/02/03) y de la matriz de requisitos. Sin auditoría no hay trazabilidad forense ni cumplimiento; es el mecanismo que soporta "no almacenar PII cruda si no es necesaria" y la investigación de incidentes (spec §11.3).

## Criterios de aceptación

- [x] Existe un modelo `AuditEvent` (append-only) con los campos mínimos del §11.2.
- [x] Existe un servicio `AuditService` con método `log(...)` que persiste un evento con timestamp UTC.
- [x] La tabla de auditoría solo permite insertar (no UPDATE/DELETE por API ni por repositorio estándar).
- [x] Se registran eventos de login exitoso/fallido, logout, refresh y registro de usuario.
- [x] Se registra el acceso a `/auth/me` (acceso a recurso protegido).
- [x] Cada evento incluye `trace_id` para correlacionar.
- [x] Los eventos NO contienen PII cruda (sin contraseñas, sin contenido de tickets).
- [x] Existe un endpoint protegido (solo supervisor/admin) para consultar eventos de auditoría, filtrado por tenant y paginado.
- [x] Los logs operativos (stdout/stderr) no exponen secretos ni contenido sensible.
- [x] Test suite cubre: creación de eventos, append-only (no se puede borrar), campos mínimos, filtrado por tenant, y que login fallido queda auditado.

## Fuera de alcance

- Integración con sistema de logging centralizado (ELK/Loki) — se deja el logging estándar y la separación de canales.
- Auditoría de eventos IA (clasificación/resumen/sugerencia). La tabla lo soporta, los eventos IA llegan en Fase 4.
- Firmado criptográfico de logs / cadena de integridad (se documenta como mejora).
- Retención/purga automática de auditoría (configurable por tenant, va con la política de retención en Fase 3).
