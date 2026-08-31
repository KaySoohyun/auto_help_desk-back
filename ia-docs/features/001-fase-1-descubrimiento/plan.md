# 001 · Fase 1: Descubrimiento y diseño de arquitectura — Plan

_Cómo se implementa lo descrito en `spec.md`. Debe respetar la `constitution/`._

## Enfoque

Feature exclusivamente de documentación. Se crea una carpeta `ia_docs/architecture/` donde viven los entregables de Fase 1 como documentos estructurados y trazables al `spec.md` (secciones 4 a 21). Cada documento se deriva directamente del spec, no se inventa contenido: si algo no está en el spec, se marca como "pendiente de decisión" en vez de asumir (regla del 80 % del AGENTS.md).

## Implementación

_Pasos técnicos concretos, en orden. Indica los archivos/módulos que se tocan._

1. Crear `ia_docs/architecture/README.md` — índice de los entregables y su trazabilidad con `spec.md`.
2. Crear `ia_docs/architecture/00-casos-de-uso-roles.md` — catálogo de casos de uso (CU-01 a CU-05), roles y flujos de gestión de tickets (del spec secciones 4 y 7).
3. Crear `ia_docs/architecture/01-matriz-requisitos.md` — matriz FR/requisitos de datos/seguridad/rendimiento trazable a secciones 8-10 y 16 del spec.
4. Crear `ia_docs/architecture/02-arquitectura-multi-tenant.md` — diagrama en Mermaid (API, persistencia, orquestador IA, auditoría, observabilidad) y decisiones de componentes (secciones 3, 14 y 16).
5. Crear `ia_docs/architecture/03-modelo-datos.md` — entidades (tenant, usuario, ticket, sugerencia IA, auditoría, feedback) y diccionario de campos con clasificación de PII (sección 9 y 11).
6. Crear `ia_docs/architecture/04-threat-model-seguridad.md` — amenazas y controles de JWT/OAuth, aislamiento por tenant, RBAC, secretos, cifrado y auditoría (sección 10).
7. Crear `ia_docs/architecture/05-politica-pii-retencion.md` — redacción, minimización y retención (sección 9.3 y 9.4).
8. Crear `ia_docs/architecture/06-estrategia-ia.md` — prompts versionados, grounding, guardrails de prompt injection y alucinación, fallback y métricas de calidad (secciones 12 y 17).
9. Crear `ia_docs/architecture/adrs/` con los ADR principales (autorización por tenant, orquestador LLM, modelo de datos) + `ADR-000-TEMPLATE.md`.
10. Crear `ia_docs/architecture/backlog-priorizado.md` — backlog de fases 2-6 derivado de `plan-ejecucion.md`.
11. Actualizar `roadmap.md` si aplica y `ia_docs/cambios.md`.

## Decisiones

_Elecciones de diseño relevantes y su justificación. Alternativas descartadas y por qué._

- **Documentación en carpeta propia `ia_docs/architecture/`** — mantiene los entregables de diseño separados del spec y de las features; facilita su revisión como artefactos de Fase 1.
- **Trazabilidad por ID del spec** — cada documento referencia las secciones del spec; evita duplicar contenido y garantiza coherencia.
- **Mermaid para diagramas** — texto versionable y legible en PR; se descartó diagramas con herramientas gráficas binarias.
- **Campos dudosos marcados como "pendiente"** — respeta la regla del 80%: no inventar decisiones de seguridad sin confirmación.

## Riesgos

- **Asumir decisiones no escritas** — mitigación: cada ADR explicita alternativas, elección y si requiere OK del usuario.
- **Documentos desalineados con el spec** — mitigación: trazabilidad por ID y revisión contra los criterios de aceptación.
- **Alcance que crece** — mitigación: solo los entregables listados en el plan; ideas extra van a backlog.