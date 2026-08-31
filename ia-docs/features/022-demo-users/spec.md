# Spec · Seed de usuarios demo

## Qué hace

Crea (semilla) usuarios demo con credenciales conocidas y tickets de ejemplo por empresa, de modo que los botones de acceso rápido del frontend (feature 014) puedan iniciar sesión al instante con cualquiera de los roles y ver una bandeja con datos.

## Contexto

- Ya existen `scripts/seed_users.py` (agente/supervisor/tenant_admin/platform_admin con `users.tenant_id` legacy) y `scripts/seed_tenants_customers.py` (tenants `test-tenant` y `acme-corp`, customers y tags).
- El registro público crea `user_tenants` (membresías) y, para `customer`, una fila en `customers` con `user_id`.
- No hay usuarios `customer` con cuenta de login ni tickets de ejemplo.

## Objetivo

1. **Usuarios demo por rol**, con membresía (`user_tenants`) en todos los tenants existentes:
   - `demo.agente@example.com` — `agent`
   - `demo.supervisor@example.com` — `supervisor`
   - `demo.admin@example.com` — `tenant_admin`
   - `demo.plataforma@example.com` — `platform_admin` (sin tenant, a nivel plataforma)
   - **Cliente demo por tenant:** `demo.cliente.<slug>@example.com` — `customer`, con su fila en `customers` (tenant del tenant correspondiente) y membresía en ese tenant.
2. **Contraseña común de demo:** `demo-pass-123` (documentada; solo demo).
3. **Tickets de ejemplo por tenant:** un puñado de tickets con estados, prioridades y categorías variadas, algunos con mensajes, algunos vinculados al cliente demo y algunos asignados al agente demo, para que la bandeja y el panel de personas tengan contenido al presentar.
4. **Idempotencia:** el script se puede correr varias veces sin duplicar (mismo criterio de los seeds actuales).

## Criterios de aceptación

1. Ejecutar `scripts/seed_demo_users.py` dos veces no duplica usuarios, membresías, customers ni tickets.
2. Cada usuario demo puede iniciar sesión en `/auth/login` con su email y `demo-pass-123` (con y sin `tenant_id`).
3. `demo.agente@example.com` + `tenant_id` de cualquier tenant existe y el login responde 200.
4. `demo.cliente.<slug>@example.com` + `tenant_id` de su tenant responde 200; su `GET /v1/me/tickets` devuelve sus tickets demo.
5. Los tickets demo quedan cifrados en reposo (se crean vía `TicketRepository`, no en crudo).
6. `platform_admin` demo entra sin tenant y puede `GET /v1/tenants` (permiso `VIEW_AUDIT`).
7. Documentado en `ia_docs/cambios.md`.
8. Suite de tests existente sigue en verde (sin regresión).

## Fuera de alcance

- Endpoints nuevos en la API (no hace falta: login real con credenciales conocidas).
- Portal de registro modificado.
- Lógica en el frontend (se cubre en la feature 014).
