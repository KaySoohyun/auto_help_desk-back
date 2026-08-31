# 021 · Portal de personas (rol customer)

**Estado:** completado

## Qué hace

Soporta el portal de usuario final (personas): un cliente registra/ingresa, crea tickets propios, los sigue y conversa con el equipo. Sin LLM en el lado cliente.

## Cambios

- **Rol `customer`**: `UserRole` + `PUBLIC_REGISTRATION_ROLES` + permiso `persona:tickets` (solo customer).
- **Perfil en `customers`**: al registrar un `customer` se crea su fila (name/email/tenant, `user_id`); migración `scripts/migrate_customers_user_id.py` (columna `customers.user_id` unique).
- **Repositorio**: `TicketRepository.list` filtra por `customer_id`; `create` acepta `customer_id`; `TicketView`/`TicketSummaryView` y schemas exponen `customer_id`.
- **Endpoints `/v1/me`** (permiso `persona:tickets`): perfil, `GET|POST /v1/me/tickets`, `GET /v1/me/tickets/{id}`, `GET|POST /v1/me/tickets/{id}/messages`. Aislamiento: 404 si el ticket no es del customer o está fuera de sus tenants.

## Verificación

- `tests/test_persona_portal.py`: 8 tests (registro + perfil, flujo crear/listar/detalle, aislamiento cross-customer y cross-tenant, mensajes, 422 en ticket cerrado, 403 para no-customer).
- Suite backend completa: **293 passed**.
