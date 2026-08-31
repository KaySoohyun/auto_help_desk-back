# 023 · Búsqueda por categorías y tags — Plan

_Cómo se implementa lo descrito en `spec.md`. Debe respetar la `constitution/`._

## Enfoque

La búsqueda se resuelve **en el backend con SQL** sobre columnas en claro, sin tocar el modelo de cifrado ni el esquema. Se agrega un parámetro `q` a los endpoints de listado y un filtro opcional `q` al repositorio de tickets, que matchea `category` (columna en claro) y el nombre de los tags del ticket (join con `ticket_tags`/`tags`). La lógica de conteo y paginado ya existente se mantiene, solo se le agrega el filtro. El frontend pasa `q` al back y elimina el filtrado en cliente.

## Implementación

_Pasos técnicos concretos, en orden. Indica los archivos/módulos que se tocan._

1. **Repositorio** — `app/repositories/tickets.py`: agregar parámetro `q: str | None` a `list()` y, cuando venga, filtrar con:
   - `Ticket.category.ilike(f"%{q}%")` **o**
   - subconsulta/`join` para tickets que tengan un tag cuyo `name` haga `ilike(f"%{q}%")` (a través de `TicketTag` → `Tag`).
   Mantener el paginado (`limit`/`offset`) y el cálculo de `total` sobre el mismo conjunto filtrado.
2. **Endpoint agente (tickets)** — `app/api/routes_tickets.py` (`GET /v1/tickets`): agregar `q: str | None = Query(default=None, max_length=...)` y pasarlo a `repo.list()`.
3. **Endpoint búsqueda agente (workspace)** — `app/api/routes_workspace.py` (`GET /v1/workspace/my-tickets`): agregar `q` y pasarlo a `repo.list()`.
4. **Endpoint persona (cliente)** — `app/api/routes_persona.py` (`GET /v1/me/tickets`): agregar `q` y pasarlo a `repo.list()`.
5. **Frontend cliente** — `src/components/features/persona/PersonasDashboard.tsx`: enviar `q` al hook `useMyTickets` (debounce), quitar el filtrado en cliente y resetear la página al buscar.
6. **Frontend agente** — conectar el input de búsqueda de la bandeja a `q` del backend (si hoy filtra en cliente).
7. **Tests** — agregar casos en `tests/` para búsqueda por categoría, por tag, sin resultados, y coexistencia con `limit/offset/status`.
8. **Documentación** — actualizar `ia_docs/cambios.md` (backend).

## Decisiones

- **Categoría y tags en SQL** — ambos en claro; evita descifrar y no cambia el esquema. El asunto/descripción se descartan por estar cifrados (ver spec, fuera de alcance).
- **`ilike` con subcadena** — simple y coincide con la expectativa "contiene el texto"; insensible a mayúsculas. Se descarta full-text de Postgres por no ser necesario para este volumen y añadir complejidad.
- **Contar y paginar sobre el mismo filtro** — reutiliza el patrón existente (`count().over()`) para que `total` sea correcto con la búsqueda activa.
- **Debounce en frontend** — para no disparar una request por tecla; mantiene la UX fluida.

## Riesgos

- **Presupuesto de la subconsulta/join de tags** — si hay muchos tickets con muchos tags, conviene una subconsulta `EXISTS` en vez de un `join` que duplique filas. Mitigación: implementar con subconsulta `EXISTS` para evitar filas duplicadas en la paginación.
- **Fuga de PII** — la búsqueda `ilike` no expone valores cifrados; solo opera sobre categoría y tags (no sensibles). Mitigación: no buscar sobre columnas cifradas.
- **Cifrado del `q`** — `q` es texto plano del usuario que se compara contra columnas en claro; no se cifra ni se busca en cifrado. Correcto por diseño.
