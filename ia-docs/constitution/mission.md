# Misión

_Define la razón de ser del proyecto. Es la referencia que decide si una feature "encaja" o no._

## Qué construimos

Un agente IA de soporte que asiste a los equipos de soporte en la gestión de tickets: clasifica automáticamente, resume el problema y sugiere respuestas editables, manteniendo controles estrictos de seguridad, privacidad, auditoría y calidad de IA.

1. **Backend multi-tenant** — API en Python/FastAPI con aislamiento por tenant, JWT/OAuth y RBAC.
2. **Orquestador de IA** — clasificación, resumen y respuesta sugerida con redacción previa de PII, guardrails contra prompt injection y alucinaciones, y aprobación humana obligatoria.
3. **Auditoría y trazabilidad** — registro de toda acción humana e IA con modelo, versión de prompt, confianza y decisión del agente.

## Para quién

- **Agente de soporte** — gestiona tickets más rápido y con consistencia; decide aceptar, editar o rechazar cada sugerencia.
- **Supervisor / Team Lead** — revisa calidad de respuestas y métricas de desempeño de IA.
- **Administrador de tenant** — configura usuarios, roles, permisos y políticas IA de su tenant.
- **Administrador de plataforma / seguridad** — supervisa auditoría, incidentes de seguridad y políticas globales de IA.

## Principios

- **Seguridad primero** — validación de tokens, autorización por tenant, secretos en vault y cifrado en tránsito y reposo.
- **La IA no actúa sola** — ninguna respuesta se envía al cliente sin aprobación humana; las acciones IA son siempre sugeridas.
- **Mínimo de datos y privacidad** — PII se redacta antes de enviar al LLM; se minimiza y se retiene solo lo necesario.
- **Confianza verificable** — grounding, nivel de confianza, fuentes y advertencias en cada sugerencia.
- **Trazabilidad total** — cada acción humana e IA queda auditada con versión de modelo y de prompt.

## Qué NO es

- No envía respuestas al cliente de forma automática.
- No ejecuta acciones autónomas ni irreversibles (reembolsos, cambios de cuenta) sin workflow explícito.
- No entrena modelos propios por tenant ni usa datos de producción para entrenamiento sin consentimiento.
- No sustituye el juicio humano del agente: todo es editable y rechazable.
- No es soporte multilingüe avanzado en el MVP.
