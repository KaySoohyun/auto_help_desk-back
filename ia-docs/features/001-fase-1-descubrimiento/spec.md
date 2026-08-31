# 001 · Fase 1: Descubrimiento y diseño de arquitectura

**Estado:** implementado ✅

## Qué hace

Producto de **solo documentación** (Fase 1 del `plan-ejecucion.md`): produce los entregables de diseño que guían todas las fases siguientes, sin escribir código de producto. Concretamente:

- Catálogo de casos de uso, roles y flujos de gestión de tickets.
- Matriz de requisitos funcionales, no funcionales, regulatorios y de seguridad.
- Diagrama de arquitectura cloud multi-tenant.
- Modelo de datos y diccionario de campos con clasificación de PII.
- Threat model y controles de JWT/OAuth, autorización por tenant y auditoría.
- Política de redacción de PII, retención y minimización de datos.
- Estrategia de prompts, grounding, control de alucinaciones y métricas de calidad IA.
- ADRs de arquitectura y backlog priorizado.

## Por qué

El `spec.md` define el *qué* y `plan-ejecucion.md` el *cuándo*, pero falta el *cómo*: decisiones de arquitectura, modelo de datos y seguridad deben quedar escritas y aprobadas antes de implementar, para no construir sobre supuestos. Es la base que la constitución exige revisar antes de tocar código.

## Criterios de aceptación

_Condiciones verificables que deben cumplirse para dar la feature por terminada. Marca `[x]` al cumplirse._

- [x] Existe un catálogo de casos de uso, roles y flujos de gestión de tickets derivado de `spec.md`.
- [x] Existe una matriz de requisitos funcionales, no funcionales, regulatorios y de seguridad trazable a `spec.md`.
- [x] Existe un diagrama de arquitectura cloud multi-tenant que incluya API, persistencia, orquestador IA y observabilidad.
- [x] Existe un modelo de datos con diccionario de campos y clasificación de PII.
- [x] Existe un threat model que cubra JWT/OAuth, aislamiento por tenant y auditoría.
- [x] Existe una política de redacción de PII, retención y minimización de datos.
- [x] Existe una estrategia de prompts, grounding, control de alucinaciones y métricas de calidad IA.
- [x] Existen ADRs de arquitectura con alternativas descartadas y backlog priorizado.
- [x] Todo documento respeta `mission.md`, `tech-stack.md` y `plan-ejecucion.md`.

## Fuera de alcance

- Escribir código de producto (API, modelos, servicios). Va en fases 2+.
- Aprovisionar infraestructura cloud. Va en Fase 2.
- Definir contratos de API finales como código. Solo se documentan las decisiones de alto nivel.
