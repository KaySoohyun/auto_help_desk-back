# Plan · Seed de usuarios demo

## Enfoque

Script standalone `scripts/seed_demo_users.py` (mismo patrón que `seed_tenants_customers.py` y `seed_users.py`): inserta directamente en la base usando los modelos y repositorios existentes, idempotente, con salida por consola.

## Piezas

### 1. Usuarios demo de soporte (compartidos)

- `DEMO_PASSWORD = "demo-pass-123"` → `hash_password`.
- Para cada tenant existente en la DB (`Tenant`):
  - `demo.agente@example.com` (agent)
  - `demo.supervisor@example.com` (supervisor)
  - `demo.admin@example.com` (tenant_admin)
  - Se crean una sola vez (por email único) y se les agrega membresía `user_tenants` por tenant con el rol correspondiente.
  - `users.tenant_id` (legacy): se setea al primer tenant solo si el usuario no tiene principal (compatibilidad con `_issue_tokens` cuando se loguea sin `tenant_id`).

### 2. Cliente demo por tenant

- `demo.cliente.<slug>@example.com` (customer).
- Crea el `User` (role `customer`), la membresía `user_tenants` para su tenant y una fila en `customers` con `user_id` (mismo criterio que el registro de la feature 021). Nombre derivado: "Cliente Demo <Tenant>".

### 3. Admin de plataforma demo

- `demo.plataforma@example.com` (platform_admin, `tenant_id=None`, sin membresías).

### 4. Tickets demo por tenant

- Por cada tenant: 4–5 tickets con `subject`/`description` realistas, `status` variado (`open`, `pending`, `waiting_customer`, `solved`), `priority` (`low`/`medium`/`high`), `category` dentro del catálogo configurado, `created_at` escalonados.
- Algunos con `customer_id` = id del cliente demo del tenant (para que el panel de personas tenga tickets).
- Algunos asignados (`assignee_id`) al usuario demo agente del tenant.
- Creación vía `TicketRepository.create` para respetar cifrado AES-GCM en `subject`/`description`.
- Mensajes opcionales vía el endpoint/repo de mensajes (o insert directo con `TicketMessage` cifrado con el repo). Si es complejo, mínimo: 1–2 tickets con un mensaje de apertura del cliente.

## Verificación

- Correr `scripts/seed_demo_users.py` (dos veces) y chequear salida idempotente.
- `curl` a `/auth/login` con cada demo user + `tenant_id` → 200; `GET /v1/me/tickets` del cliente demo → sus tickets.
- `platform_admin` demo → `GET /v1/tenants` 200.
- `.venv/bin/python -m pytest -q` en verde.

## Nota

- Las credenciales demo son públicas por diseño (producto de presentación). Se documentan en el script y en `cambios.md`; **no** en `.env` ni en variables de producción.
