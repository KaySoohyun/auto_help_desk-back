# 003 · Autorización por tenant y RBAC

**Estado:** implementado ✅

## Qué hace

Capa de autorización de la plataforma (Fase 2, épicas 2.2/2.3 del plan de ejecución). Sobre la autenticación JWT ya implementada (feature 002), agrega:

- **Aislamiento por tenant obligatorio**: cada request valida que el `tenant_id` del token coincide con el recurso que pide; toda consulta a la DB se filtra por tenant (ADR-001).
- **RBAC**: permisos por rol (`platform_admin`, `tenant_admin`, `supervisor`, `agent`) sobre las capacidades clave del spec §10.3.
- **Rutas protegidas con roles**: decorador/dependencia `require_roles` que rechaza con 403 cuando el rol no tiene permiso.
- **Filtro por tenant en repositorio**: capa de datos que inyecta `WHERE tenant_id = :current` en toda tabla de negocio (base para RLS futuro).

## Por qué

Es el segundo pilar de seguridad del spec (§10.2, §10.3). Sin autorización por tenant, el aislamiento es solo cosmético; sin RBAC, cualquier usuario con token podría operar con todos los permisos. Habilita además los tests de aislamiento multi-tenant (spec §19.2).

## Criterios de aceptación

- [x] Existe un módulo de permisos que mapea cada rol a las capacidades del spec §10.3 (leer tickets, solicitar IA, editar/enviar respuestas, configurar tenant, ver auditoría, gestionar políticas IA).
- [x] Existe una dependencia `require_roles(*roles)` que valida el rol del token y devuelve 403 si no tiene permiso.
- [x] Existe un repositorio central que aplica filtro por `tenant_id` obligatorio en toda consulta a tablas de negocio (invariante ADR-001).
- [x] El `tenant_id` se toma siempre del token validado, nunca de inputs del cliente (spec §10.2).
- [x] Un endpoint protegido con `require_roles` responde 401 sin token y 403 con rol insuficiente.
- [x] Un usuario de tenant A no puede acceder a recursos de tenant B (test de aislamiento).
- [x] Los endpoints de auth de la feature 002 siguen funcionando (regresión).
- [x] Test suite con pytest cubre permisos, filtro por tenant y aislamiento.

## Fuera de alcance

- RLS real en PostgreSQL (se documenta como recomendación; el filtro en repositorio es el mecanismo del MVP).
- Gestión completa de usuarios por tenant (CRUD de usuarios). Se expone lo mínimo necesario para probar RBAC.
- Permisos finos por endpoint de negocio (tickets, IA). Solo se implementa el mecanismo y un ejemplo concreto (`/users` y un endpoint de prueba).
- Auditoría de eventos (feature 005).
