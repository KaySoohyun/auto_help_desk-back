# 006 · API core de tickets

**Estado:** implementado (pendiente merge a develop)

## Qué hace

API de gestión de tickets (Fase 3, épica 3.1 del plan de ejecución) con aislamiento por tenant obligatorio (ADR-001). Permite:

- **Crear** un ticket (asunto, descripción, categoría, prioridad, idioma).
- **Consultar** un ticket por ID.
- **Listar** tickets del tenant con filtros (estado, categoría, prioridad, asignado a, rango de fecha) y paginación.
- **Actualizar** campos editables (estado, prioridad, categoría, asignación).
- **Agregar mensajes** al historial de conversación del ticket.
- **Cerrar** un ticket.

Cada operación registra un evento de auditoría (reuso de `AuditService`, feature 005) y se filtra por el `tenant_id` del token. La descripción y los mensajes son candidatos a cifrado con `crypto` (feature 004) — se define en el plan cómo aplicarlo.

## Por qué

Es el núcleo de datos del producto (spec §9.1, FR-10) y la base sobre la que operan la IA (Fase 4) y el workspace de agente (Fase 5). Sin la API de tickets, las siguientes fases no tienen dominio sobre el que trabajar.

## Criterios de aceptación

- [ ] `POST /v1/tickets` crea un ticket (asunto, descripción obligatorios; categoría/prioridad/idioma opcionales) y lo asigna al tenant del token.
- [ ] `GET /v1/tickets/{id}` devuelve el ticket solo si pertenece al tenant del usuario (otro tenant → 404).
- [ ] `GET /v1/tickets` lista tickets del tenant con filtros y paginación (`limit`, `offset`).
- [ ] `PATCH /v1/tickets/{id}` actualiza estado, prioridad, categoría y/o asignación.
- [ ] `POST /v1/tickets/{id}/messages` agrega un mensaje al historial.
- [ ] `POST /v1/tickets/{id}/close` cierra el ticket (requiere rol agente/supervisor/admin).
- [ ] Toda escritura registra evento de auditoría con `trace_id`.
- [ ] La descripción y los mensajes se cifran con `crypto.encrypt_field` antes de persistir y se descifran al leer.
- [ ] La PII de los campos cifrados no aparece en claro en la DB (test).
- [ ] Aislamiento: usuario de tenant A no ve/edita tickets de tenant B (test).
- [ ] Test suite cubre CRUD, mensajes, cierre, cifrado, aislamiento y auditoría.

## Fuera de alcance

- Clasificación/resumen/respuesta IA (Fase 4).
- Redacción de PII para LLM (feature 007) — aquí solo cifrado en reposo.
- Optimización de consultas/caché (feature 008).
- Búsqueda full-text y observabilidad (features 008/009).
- Adjuntos y documentos indexables (fuera del MVP base de tickets).
