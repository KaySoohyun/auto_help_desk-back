# Modelos de Datos — Auto Help Desk

Modelos SQLAlchemy del backend. Toda tabla está en el esquema SQLite por defecto (`app.db`).
Los campos marcados como **cifrados** se guardan cifrados en reposo (clave derivada de `SECRET_KEY`); la API siempre devuelve el valor descifrado.

---

## `users`

Usuarios del sistema.

| Columna | Tipo | Restricciones | Notas |
| --- | --- | --- | --- |
| `id` | int | PK | |
| `email` | string(255) | unique, index | |
| `password_hash` | string(255) | | Hash Argon2; nunca se expone |
| `role` | string(50) | | `platform_admin` \| `tenant_admin` \| `supervisor` \| `agent` |
| `tenant_id` | string(64) | nullable, index | `null` para admins multi-tenant |
| `is_active` | bool | default `true` | Si es `false`, no puede autenticarse |
| `created_at` | datetime (tz) | default now(UTC) | |

---

## `tickets`

Tickets de soporte por tenant.

| Columna | Tipo | Restricciones | Notas |
| --- | --- | --- | --- |
| `id` | int | PK | |
| `tenant_id` | string(64) | index | Filtro de aislamiento por tenant |
| `subject` | text | **cifrado** | |
| `description` | text | **cifrado**, carga diferida | No se incluye en listados |
| `category` | string(100) | nullable, index | |
| `priority` | string(20) | nullable, index | `low` \| `medium` \| `high` \| `urgent` |
| `language` | string(10) | default `"es"` | |
| `status` | string(20) | index, default `"open"` | `open` \| `in_progress` \| `on_hold` \| `closed` |
| `assignee_id` | int | FK `users.id`, nullable, index | |
| `created_at` | datetime (tz) | default now(UTC) | |
| `updated_at` | datetime (tz) | onupdate now(UTC) | |

Índices compuestos: `(tenant_id, status)`, `(tenant_id, created_at)`, `(tenant_id, priority)`.

---

## `ticket_messages`

Mensajes dentro de un ticket.

| Columna | Tipo | Restricciones | Notas |
| --- | --- | --- | --- |
| `id` | int | PK | |
| `ticket_id` | int | FK `tickets.id` (ON DELETE CASCADE), index | |
| `author_id` | int | FK `users.id`, nullable | |
| `body` | text | **cifrado**, carga diferida | |
| `created_at` | datetime (tz) | default now(UTC) | |

Índice compuesto: `(ticket_id, created_at)`.

---

## `refresh_tokens`

Tokens de refresco para rotación/revocación.

| Columna | Tipo | Restricciones | Notas |
| --- | --- | --- | --- |
| `jti` | string(36) | PK | Identificador único del refresh (claim JWT) |
| `user_id` | int | FK `users.id`, index | |
| `expires_at` | datetime (tz) | | |
| `revoked` | bool | default `false` | |
| `revoked_at` | datetime (tz) | nullable | |
| `created_at` | datetime (tz) | default now(UTC) | |

Cada uso de `/auth/refresh` revoca el token anterior (rotación de un solo uso).

---

## `ai_suggestions`

Sugerencias de IA por ticket. Una sola tabla para todos los tipos.

| Columna | Tipo | Restricciones | Notas |
| --- | --- | --- | --- |
| `id` | int | PK | |
| `tenant_id` | string(64) | index | |
| `ticket_id` | int | FK `tickets.id` (ON DELETE CASCADE), index | |
| `type` | string(32) | | `classification` \| `summary` \| `reply` |
| `output` | JSON | | Salida estructurada **sin PII** según tipo |
| `confidence` | float | nullable | 0.0–1.0 |
| `model` | string(128) | nullable | Modelo LLM usado |
| `prompt_version` | string(32) | nullable | |
| `state` | string(20) | default `"draft"` | `draft` \| `accepted` \| `edited` \| `rejected` \| `flagged` |
| `created_at` | datetime (tz) | default now(UTC) | |
| `updated_at` | datetime (tz) | onupdate now(UTC) | |

Índice compuesto: `(tenant_id, ticket_id)`.

Contenido de `output` por tipo:
- `classification`: `{ category, subcategory, intent, suggested_priority, rationale }`
- `summary`: `{ summary, missing_information }`
- `reply`: `{ suggested_reply, sources, policy_flags }`

---

## `feedback`

Feedback del agente sobre una sugerencia de IA (1:1 con `ai_suggestions.id`).

| Columna | Tipo | Restricciones | Notas |
| --- | --- | --- | --- |
| `id` | int | PK | |
| `suggestion_id` | int | FK `ai_suggestions.id` (ON DELETE CASCADE), unique, index | |
| `tenant_id` | string(64) | index | |
| `action` | string(20) | | `accepted` \| `edited` \| `rejected` \| `flagged` |
| `reason` | text | nullable | Nunca se envía al LLM ni a auditoría |
| `edited_content_hash` | string(128) | nullable | Hash del contenido editado |
| `created_at` | datetime (tz) | default now(UTC) | |
| `updated_at` | datetime (tz) | onupdate now(UTC) | |

Índice compuesto: `(tenant_id, suggestion_id)`.

---

## `audit_events`

Auditoría **append-only** (solo se inserta; nunca se actualiza ni elimina). No almacena PII ni secretos.

| Columna | Tipo | Restricciones | Notas |
| --- | --- | --- | --- |
| `id` | int | PK | |
| `created_at` | datetime (tz) | default now(UTC) | |
| `tenant_id` | string(64) | nullable, index | |
| `user_id` | int | nullable, index | |
| `action` | string(100) | index | Ej.: `ticket.created`, `auth.login_success`, `ai.classified` |
| `service` | string(64) | nullable | `auth` \| `tickets` \| `admin` \| `ai` \| `audit` \| `pii` |
| `model` | string(64) | nullable | Ej.: `Ticket`, `AISuggestion` |
| `model_version` | string(64) | nullable | |
| `prompt_version` | string(64) | nullable | |
| `trace_id` | string(64) | index | Correlación por request |
| `result` | string(20) | | `success` \| `failure` \| `disabled` |
| `confidence` | float | nullable | |
| `detail` | JSON | nullable | Contexto no sensible (ids, acción, modelo, versión) |

Índice compuesto: `(tenant_id, created_at)`.

---

## `tenant_policies`

Políticas IA por tenant (una fila por tenant).

| Columna | Tipo | Restricciones | Notas |
| --- | --- | --- | --- |
| `id` | int | PK | |
| `tenant_id` | string(64) | unique, index | |
| `ai_enabled` | bool | default `true` | Kill-switch por tenant |
| `tone` | string(50) | nullable | Tono de respuesta |
| `language` | string(10) | nullable | Idioma preferido |
| `allowed_categories` | JSON | nullable | Lista de categorías permitidas |
| `escalation_rules` | JSON | nullable | Reglas de escalamiento |
| `created_at` | datetime (tz) | default now(UTC) | |
| `updated_at` | datetime (tz) | onupdate now(UTC) | |

Si no existe fila para un tenant, el default es `ai_enabled: true` (se aplica en el servicio, no se persiste).

---

## `global_policies`

Overrides globales de IA. **Fila única** (`id=1`). Campos `null` = usar default de `.env`.

| Columna | Tipo | Restricciones | Notas |
| --- | --- | --- | --- |
| `id` | int | PK | Siempre `1` |
| `llm_model` | string(128) | nullable | |
| `ai_confidence_threshold` | float | nullable | 0.0–1.0 |
| `guardrails_enabled` | bool | nullable | |
| `llm_rate_max_calls` | int | nullable | |
| `updated_at` | datetime (tz) | onupdate now(UTC) | |

Los valores efectivos que consume la API se calculan en runtime: override de `GlobalPolicy` → default de `.env` (`settings`).

---

## Relaciones

```
User 1──N RefreshToken
User 1──N TicketMessage (author)
User 1──N Ticket (assignee)

Tenant (1) ──N Ticket
Ticket 1──N TicketMessage
Ticket 1──N AISuggestion
AISuggestion 1──1 Feedback

User 1──N AuditEvent
TenantPolicy (1 por tenant)
GlobalPolicy (1 fila global)
```
