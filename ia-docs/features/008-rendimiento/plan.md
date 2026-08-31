# 008 · Optimización de consultas y rendimiento — Plan

_Cómo se implementa lo descrito en `spec.md`._

## Enfoque

Cambios declarativos en los modelos SQLAlchemy (índices compuestos + columnas diferidas) para que las consultas del repositorio de tickets se vuelvan eficientes sin tocar la lógica de negocio ni la API. Se valida con tests de schema y regresión completa.

## Implementación

1. **Índices compuestos** en `app/models/ticket.py`:
   - `Ticket.__table_args__` con `Index("ix_tickets_tenant_status", "tenant_id", "status")`,
     `Index("ix_tickets_tenant_created", "tenant_id", "created_at")`,
     `Index("ix_tickets_tenant_priority", "tenant_id", "priority")`.
   - `TicketMessage.__table_args__`: `Index("ix_messages_ticket_created", "ticket_id", "created_at")`.
   - Mantener los índices por columna existentes (no los borro para no romper queries actuales).
   - En `AuditEvent` (app/models/audit.py): `Index("ix_audit_tenant_created", "tenant_id", "created_at")`.

2. **Columnas diferidas**:
   - `Ticket.description`: `mapped_column(Text, deferred=True)`.
   - `TicketMessage.body`: `mapped_column(Text, deferred=True)`.
   - El repositorio `TicketRepository.list()` no necesita cambios: SQLAlchemy no carga las columnas diferidas en el `select` normal. `get_or_none`, `update` y los mensajes los cargan al pedirlos explícitamente (se sigue devolviendo `description`/`body` en esas rutas porque el tipo ORM las expone al acceder).

3. **Sanidad de `list()`**: verificar que al construir `TicketView` no se acceda a `description` en el listado (ok: `_view` copia de atributos ORM; con deferred, acceder dispara lazy load. Para garantizar que listado no carga, se construye el view con los valores ya materializados sin tocar `description` — se revisa en implementación. Si queda un acceso, se usa `undefer` solo en las rutas de detalle).

4. **Test de schema**: verificar mediante `inspect(engine).get_indexes("tickets")` que existen los índices compuestos; y `deferred` de `description`/`body` (utilizando `Ticket.__mapper__.columns['description'].deferred`).

5. Suite completa de 68 tests debe seguir pasando (sin regresión).

## Riesgos

- **Deferred y `model_dump`/Pydantic** — si una ruta serializa sin acceso previo, el deferred no se materializa. Mitigación: `_view` accede a `description` SOLO en get/detalle; tests lo validan. La ser de respuesta `TicketOut` se construye desde el view ya materializado.
- **Deferred en tests de cifrado** — los tests leen `description` directamente de la DB; con deferred, al acceder se dispara load lazy, sigue funcionando pero en el test hay que tener sesión activa. Revisar `test_tickets.py` (`SessionLocal`).
- **Índices por columna duplicados** — compuestos plus simples; SQLite tolera; se documenta para no duplicar en prod.