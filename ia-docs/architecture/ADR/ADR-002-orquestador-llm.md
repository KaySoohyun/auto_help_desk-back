# ADR-002 · Orquestador LLM como punto único con abstracción mínima

**Estado:** aceptado

## Contexto

La integración con el LLM (spec §14.2) debe soportar timeouts, reintentos, versionado de modelos y guardrails. El MVP (§20.2) no requiere múltiples proveedores simultáneos, pero sí una abstracción mínima para no acoplarse.

## Decisión

Se implementa un **módulo orquestador de IA único dentro del backend (FastAPI)** que:

- Centraliza conexión al LLM, selección de modelo por tarea, versionado, timeouts y reintentos.
- Recibe contexto **ya redactado** (nunca PII cruda).
- Aplica guardrails de entrada y salida (§12) y devuelve salida estructurada validada.
- Registra métricas de tokens, latencia y costo si aplica (§14.2) y audita cada llamada (§11).
- Expone solo la interfaz interna (clasificar / resumir / sugerir); el resto del sistema no conoce al proveedor.

## Alternativas consideradas

- **Integración directa en cada servicio** — acoplamiento al proveedor y duplicación de guardrails; descartada.
- **Microservicio separado de IA** — aísla el dominio, pero añade complejidad de red/deploy para el MVP; se difiere como evolución.
- **Multi-proveedor simultáneo desde el inicio** — no es necesario para MVP (§20.2); se cubre con la abstracción mínima.

## Consecuencias

- Punto único para seguridad (guardrails) y para métricas/costos.
- El dominio IA queda acotado; cambiarlo no afecta al resto del backend.
- El backend necesita un proveedor configurado vía env/secrets; se define el modelo concreto en Fase 4.

## Estado

- [ ] Propuesto
- [x] Aceptado
- [ ] Rechazado

## Referencias

- `spec.md` §12, §14.2, §16.3, §20.2.
- `ia_docs/architecture/02-arquitectura-multi-tenant.md` D-03.
- `ia_docs/architecture/06-estrategia-ia-guardrails.md`.