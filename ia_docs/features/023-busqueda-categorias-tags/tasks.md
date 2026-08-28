# 023 · Búsqueda por categorías y tags — Tareas

_Checklist accionable derivada del `plan.md`. Tareas pequeñas y concretas; marca `[x]` al completarlas._

## Backend

- [ ] `app/repositories/tickets.py`: agregar `q: str | None` a `list()` con filtro por `category.ilike` y subconsulta `EXISTS` sobre tags (`ticket_tags` → `tags.name.ilike`).
- [ ] Mantener paginado (`limit`/`offset`) y `total` correctos al estar `q` activo.
- [ ] `app/api/routes_tickets.py` (`GET /v1/tickets`): agregar query param `q` y pasarlo al repo.
- [ ] `app/api/routes_workspace.py` (`GET /v1/workspace/my-tickets`): agregar query param `q` y pasarlo al repo.
- [ ] `app/api/routes_persona.py` (`GET /v1/me/tickets`): agregar query param `q` y pasarlo al repo.

## Frontend

- [ ] Cliente (`PersonasDashboard.tsx`): enviar `q` al hook con debounce, resetear página al buscar y quitar el filtrado en cliente.
- [ ] Agente: conectar el input de búsqueda de la bandeja a `q` del backend.

## Pruebas

- [ ] Test backend: búsqueda por categoría (subcadena, case-insensitive).
- [ ] Test backend: búsqueda por tag.
- [ ] Test backend: búsqueda sin resultados devuelve lista vacía y `total = 0`.
- [ ] Test backend: `q` coexiste con `status`/`category`/`priority`/`limit`/`offset`.
- [ ] `pnpm lint` y `pnpm typecheck` en frontend; `pytest -q` en backend.
- [ ] Validar contra los criterios de aceptación de `spec.md`.
- [ ] Actualizar `ia_docs/cambios.md`.
- [ ] Mover la feature a "Hecho" en `../../constitution/roadmap.md`.
