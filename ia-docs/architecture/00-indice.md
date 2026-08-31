# Índice de Arquitectura

> Entregables de la Fase 1 (Descubrimiento y diseño) según `ia_docs/plan-ejecucion.md`. Cada documento referencia los ID del `ia_docs/spec.md` de los que se deriva.

| # | Documento | Trazabilidad (spec) |
|---|---|---|
| 00 | [Casos de uso, roles y flujos](./00-casos-de-uso-roles-flujos.md) | §4, §7, §14.1 |
| 01 | [Matriz de requisitos](./01-matriz-requisitos.md) | §5, §6, §8, §9, §10, §16 |
| 02 | [Arquitectura multi-tenant](./02-arquitectura-multi-tenant.md) | §3, §14, §16 |
| 03 | [Modelo de datos y PII](./03-modelo-datos-pii.md) | §4, §9, §11 |
| 04 | [Threat model y seguridad](./04-threat-model-seguridad.md) | §10, §12, §18 |
| 05 | [Política de PII, retención y minimización](./05-politica-pii-retencion.md) | §9.2, §9.3, §9.4, §11 |
| 06 | [Estrategia de IA y guardrails](./06-estrategia-ia-guardrails.md) | §12, §15, §17 |
| ADR | [Decisiones de arquitectura](./ADR/) | §18, §20 |
| 07 | [Backlog priorizado](./07-backlog-priorizado.md) | `plan-ejecucion.md` |

## Estado de las decisiones

Cada ADR puede estar en uno de estos estados:

- **Aceptado** — decisión tomada, implementar en fases siguientes.
- **Propuesto** — documentado, requiere OK del usuario.
- **Rechazado** — evaluado y descartado; se registra la alternativa.