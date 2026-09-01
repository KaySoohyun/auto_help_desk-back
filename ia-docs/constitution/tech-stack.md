# Tech stack y convenciones

_Cómo está construido el proyecto y las reglas que todo el código debe respetar. Es la referencia técnica que ningún plan de feature debería contradecir._

## Tecnologías

- **Lenguaje:** Python 3.x
- **Framework / runtime:** FastAPI
- **Base de datos:** SQLAlchemy 2.x (Pydantic v2 para validación; `DATABASE_URL` configurable, p. ej. SQLite en local, PostgreSQL en producción)
- **Configuración:** pydantic-settings leyendo variables desde `.env`
- **Autenticación:** JWT HS256 de emisión propia (PyJWT) con `sub`, `tenant_id` (opcional) y `roles`; refresh rotativo y revocación. OIDC/OAuth 2.0 diferido (ADR-005)
- **Arquitectura:** cloud multi-tenant (landing zone y entornos base aprovisionados como código — Fase 2 del plan de ejecución)
- **Integración IA:** orquestador LLM con gateway de timeouts, reintentos, fallback, rate limit por tenant+usuario y plantillas de prompt versionadas; proveedor mock determinista y HTTP (OpenAI-compatible)
- **Tests:** suite `pytest` en `tests/` (ver `AGENTS.md`)
- **Despliegue:** CI/CD en `.github/workflows/ci.yml` (tests, compileall, chequeo de secretos, smoke `/health`, release con gate) + `scripts/release.sh` (tag `vX.Y.Z`)

## Archivos / módulos clave

_Mapa breve de dónde vive cada cosa. Solo lo que un recién llegado necesita para orientarse._

- `ia-docs/spec.md` — especificación funcional completa del producto.
- `ia-docs/plan-ejecucion.md` — plan de ejecución en 6 fases con épicas y entregables.
- `ia-docs/constitution/` — misión, roadmap y tech stack (la constitución manda).
- `ia-docs/features/` — specs de features (cada una con `spec.md`, `plan.md` y `tasks.md`).
- `ia-docs/architecture/` — ADRs y documentos de arquitectura.
- `ia-docs/post-code/models.md` y `post-code/api.md` — modelo de datos y referencia de API.
- `ia-docs/cambios.md` — registro de todos los cambios del proyecto.
- `app/api/` — routers (auth, tickets, workspace, admin, ai, kb, tags, agents, customers, persona, tenants, audit, pii, metrics).
- `app/models/` — modelos SQLAlchemy.
- `app/schemas/` — schemas Pydantic v2.
- `.env` / `.env.example` — configuración de secretos y conexión (`.env` no se sube al repo).

## Comandos

- Dev: `.venv/bin/uvicorn app.main:app --reload` (requiere `.env`; DB por `DATABASE_URL`)
- Tests: `.venv/bin/python -m pytest -q`
- Chequeo de sintaxis: `.venv/bin/python -m compileall -q app tests scripts`
- Chequeo de secretos: `bash scripts/check_secrets.sh`
- Release (crea tag `vX.Y.Z`): `bash scripts/release.sh [--push]`
- Health check: `curl -s localhost:8000/health`

## Modelo de datos / dominio

- **Tenant** — unidad de aislamiento; toda consulta y escritura debe filtrarse obligatoriamente por tenant.
- **Usuario** — identidad autenticada vía JWT con rol (`agent`, `supervisor`, `tenant_admin`, `platform_admin`, `customer`); pertenece a uno o más tenants vía `user_tenants`.
- **Ticket** — entidad central gestionada; asunto, descripción (cifrados), historial, estado (`open|in_progress|on_hold|closed`), categoría, prioridad y customer opcional.
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
