# Tasks · Seed de usuarios demo

Estado: ☐ pendiente · ☐ en curso · ☑ hecho

- [x] ☐ Crear `scripts/seed_demo_users.py`:
  - [x] ☐ Usuarios demo de soporte (agente/supervisor/tenant_admin) con membresías en todos los tenants existentes.
  - [x] ☐ Cliente demo por tenant (`demo.cliente.<slug>@example.com`) con fila en `customers` y membresía.
  - [x] ☐ Admin de plataforma demo (sin tenant).
  - [x] ☐ Tickets demo por tenant (creados vía `TicketRepository` para cifrado), con estados/prioridades/categorías variadas, algunos vinculados al cliente demo y asignados al agente demo; algunos con mensajes.
  - [x] ☐ Idempotencia (sin duplicar al re-ejecutar).
- [x] ☐ Ejecutar el script dos veces y verificar que no duplica.
- [x] ☐ Verificar login con `demo.*@example.com` / `demo-pass-123` (con y sin `tenant_id`) contra FastAPI.
- [x] ☐ Verificar `GET /v1/me/tickets` del cliente demo y `GET /v1/tenants` del platform_admin demo.
- [x] ☐ `.venv/bin/python -m pytest -q` en verde (sin regresión).
- [x] ☐ Documentar en `ia_docs/cambios.md` (credenciales demo y cómo correr el seed).
- [x] ☐ Mover la feature a "Hecho" en `constitution/roadmap.md`.
