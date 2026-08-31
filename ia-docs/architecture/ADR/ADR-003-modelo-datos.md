# ADR-003 · Modelo de datos: entidades mínimas y tenant_id en toda tabla

**Estado:** aceptado

## Contexto

El spec define las entidades centrales (tickets, sugerencias IA, feedback, auditoría, config de tenant) y exige aislamiento, trazabilidad y redacción de PII (§4, §9, §11). Hay que fijar el esquema mínimo para no sobre-modelar en Fase 1 ni quedarnos cortos para Fases 3-5.

## Decisión

Se adopta el esquema de `ia_docs/architecture/03-modelo-datos-pii.md` con estas reglas:

- **`tenant_id` en toda tabla de negocio** (tickets, config, sugerencias, auditoría, KB) salvo `user` que se referencia por rol.
- **Sugerencia IA** lleva `type`, `output`, `confidence`, `model`, `prompt_version`, `state` y opcional `kb_article_id` (grounding).
- **Auditoría** es `append-only` con `created_at` UTC, `trace_id`, `action`, `model`, `prompt_version`.
- **Redacción**: los campos CRÍTICOS se clasifican; nunca se persisten en formato crudo en logs de IA.

## Alternativas consideradas

- **Tabla única "eventos" genérica para auditoría** — flexible pero sin schema semántico; descartada por trazabilidad explícita.
- **Separar sugerencia por tipo (classify/summary/reply)** — más tablas sin valor real para MVP; descartado, se usa `type`.
- **Almacenar el mapeo token→PII en el ticket** — se decide que vive en el servicio de redacción (§3, ADR-005 pendiente) y no en el modelo.

## Consecuencias

- Esquema mínimo y estable para comenzar Fase 3; cada nueva entidad pasa por este ADR.
- La trazabilidad de IA (FR-09) queda soportada desde el modelo.
- Invariante: cualquier tabla nueva con datos de negocio debe incluir `tenant_id` y pasar por el repositorio (ADR-001).

## Estado

- [ ] Propuesto
- [x] Aceptado
- [ ] Rechazado

## Referencias

- `spec.md` §4, §9, §11.
- `ia_docs/architecture/03-modelo-datos-pii.md`.
- ADR-001.