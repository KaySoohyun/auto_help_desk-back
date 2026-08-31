# 07 · Backlog priorizado

> Derivado de `ia_docs/plan-ejecucion.md`. Ordena las fases por dependencia: cada fase prepara a la siguiente. Prioridad P0 (crítico) → P3 (diferible).

## Priorización

| Prioridad | Fase | Contenido resumido | Por qué ahora |
|---|---|---|---|
| P0 | Fase 2 | Autenticación JWT/OAuth, autorización por tenant + RBAC, cifrado/secretos, auditoría | Sin identidad y aislamiento no puede construirse nada sobre datos |
| P0 | Fase 3 | API core de tickets, persistencia multi-tenant, redacción PII, optimización de consultas, observabilidad | El núcleo de datos y su aislamiento son la base del producto |
| P1 | Fase 4 | Orquestador LLM, clasificación, resumen, sugerencia, guardrails, suite de evaluación | El valor IA llega después de que existan tickets y redacción |
| P1 | Fase 5 | Workspace de agente, panel IA, admin de tenant, auditoría | Sin la UX no se puede operar el valor IA |
| P2 | Fase 6 | Pruebas E2E, pentest, red team IA, rendimiento, CI/CD, runbooks | Defensa en profundidad y operación; depende de lo anterior |
| P3 | Fase 7+ | RAG avanzado, multi-idioma, tickets duplicados, analítica por agente/equipo | Post-MVP, ideas del spec §21 y del roadmap |

## Detalle Fase 2 (siguiente a implementar)

| ID | Entregable | Requisito base |
|---|---|---|
| 2.1 | Infraestructura base / landing zone | §10 |
| 2.2 | Autenticación JWT/OAuth (ADR-005) | §10.1 |
| 2.3 | Autorización por tenant y RBAC (ADR-001) | §10.2, §10.3 |
| 2.4 | Cifrado en tránsito y reposo, secretos en vault | §10.4, §10.5 |
| 2.5 | Auditoría, logging y trazabilidad | §11 |

## Criterios para mover un item

1. Cumple los criterios de aceptación de su spec de feature.
2. Pasa las pruebas de aislamiento multi-tenant (§19.2).
3. Documentado en `ia_docs/cambios.md` y reflejado en `constitution/roadmap.md`.