# Tech stack y convenciones

_Cómo está construido el proyecto y las reglas que todo el código debe respetar. Es la referencia técnica que ningún plan de feature debería contradecir._

## Tecnologías

- **Lenguaje:** Python 3.x
- **Framework / runtime:** FastAPI
- **Base de datos:** SQLAlchemy 2.x (Pydantic v2 para validación; `DATABASE_URL` configurable, p. ej. SQLite en local, PostgreSQL en producción)
- **Configuración:** pydantic-settings leyendo variables desde `.env`
- **Autenticación:** JWT (OIDC / OAuth 2.0) con expiración, issuer, audiencia y claims mínimos; scopes y revocación
- **Arquitectura:** cloud multi-tenant (landing zone y entornos base aprovisionados como código — Fase 2 del plan de ejecución)
- **Integración IA:** orquestador LLM con gateway de timeouts, reintentos, fallback y límites de uso; plantillas de prompt versionadas
- **Tests:** por definir en `AGENTS.md` (`Comandos` está pendiente)
- **Despliegue:** CI/CD con rollout por tenants, feature flags y rollback (Fase 6 del plan de ejecución)

## Archivos / módulos clave

_Mapa breve de dónde vive cada cosa. Solo lo que un recién llegado necesita para orientarse._

- `ia_docs/spec.md` — especificación funcional completa del producto.
- `ia_docs/plan-ejecucion.md` — plan de ejecución en 6 fases con épicas y entregables.
- `ia_docs/constitution/` — misión, roadmap y tech stack (la constitución manda).
- `ia_docs/features/` — specs de features (cada una con `spec.md`, `plan.md` y `tasks.md`).
- `ia_docs/cambios.md` — registro de todos los cambios del proyecto.
- `.env` / `.env.example` — configuración de secretos y conexión (`.env` no se sube al repo).

## Comandos

- `<comando dev>` — pendiente de definir.
- `<comando test>` — pendiente de definir.
- `<comando lint>` — pendiente de definir.
- `<comando build>` — no aplica (aplicación interpretada).

## Modelo de datos / dominio

_Documenta solo lo no obvio: invariantes, mecánicas especiales, qué campo controla qué. Se detallará con el modelo de datos en Fase 1/3 del plan de ejecución._

- **Tenant** — unidad de aislamiento; toda consulta y escritura debe filtrarse obligatoriamente por tenant.
- **Usuario** — identidad autenticada vía JWT/OAuth con rol (agente, supervisor, admin de tenant, admin de plataforma, servicio IA).
- **Ticket** — entidad central gestionada; debe conservar asunto, descripción, historial, estado, categoría, prioridad y metadatos mínimos.
- **Sugerencia IA** — clasificación/resumen/respuesta con versión de modelo y prompt, confianza, fuentes, warnings y estado final (aceptada/editada/rechazada).
- **Evento de auditoría** — timestamp UTC, tenant, user/service, ticket, acción, modelo, versión de prompt, trace ID, resultado y confianza.

## Convenciones

- Nombres de variables y funciones en inglés; comentarios y documentación en español si son necesarios.
- Tipado de Python en todo el código; Pydantic v2 para schemas y validación; SQLAlchemy 2.x para persistencia.
- Configuración siempre desde `.env` vía pydantic-settings; nunca secretos hardcodeados.
- Seguridad prioritaria: validación de tokens, expiración, scopes y revocación; autorización por tenant en cada request.
- Mantener el código simple y legible; no añadir funcionalidades fuera de lo pedido; no inventar dependencias.

## Estilo visual

_No aplica en el MVP: proyecto de backend. La UI del agente (workspace y panel IA) se especificará cuando se aborde la Fase 5._

## Límites duros

- No subir `.env*` ni secretos al repo.
- No exponer API keys de LLM en frontend ni en logs; secrets en vault.
- Nunca enviar PII cruda al LLM: redacción obligatoria antes de la llamada.
- Nunca enviar respuestas IA al cliente sin aprobación humana.
- Toda interacción IA debe quedar auditada con versión de modelo y de prompt.
- No añadir dependencias fuera del stack definido sin avisar.
- No ejecutar acciones autónomas ni irreversibles desde la IA.
