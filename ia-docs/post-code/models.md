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
| `name` | string(255) | nullable | Nombre de display (`migrate_users_name.py` lo backfillea desde el email) |
| `password_hash` | string(255) | | Hash Argon2; nunca se expone |
| `role` | string(50) | | `platform_admin` \| `tenant_admin` \| `supervisor` \| `agent` \| `customer` |
| `tenant_id` | string(64) | nullable, index | Legacy (un solo tenant); la membresía real es vía `user_tenants` |
| `is_active` | bool | default `true` | Si es `false`, no puede autenticarse |
| `created_at` | datetime (tz) | default now(UTC) | |

---

## `tenants`

Empresas multi-tenant.

| Columna | Tipo | Restricciones | Notas |
| --- | --- | --- | --- |
| `id` | string(64) | PK | |
| `name` | string(100) | | |
| `slug` | string(100) | unique, index | Primer segmento de la URL (`/[slug]/...`) |
| `created_at` | datetime (tz) | default now(UTC) | |

---

## `user_tenants`

Membresía many-to-many usuario ↔ tenant (rollo por tenant, feature 019). El `users.tenant_id` legacy se mantiene por compatibilidad.

| Columna | Tipo | Restricciones | Notas |
| --- | --- | --- | --- |
| `id` | int | PK | |
| `user_id` | int | FK `users.id` (CASCADE), index | |
| `tenant_id` | string(64) | FK `tenants.id` (CASCADE), index | |
| `role` | string(50) | | Rol del usuario en **este** tenant |
| `created_at` | datetime (tz) | default now(UTC) | |

Índice único compuesto: `(user_id, tenant_id)`.

---

## `customers`

Clientes del portal de personas (una fila por persona, vinculada a `users.id`).

| Columna | Tipo | Restricciones | Notas |
| --- | --- | --- | --- |
| `id` | int | PK | |
| `tenant_id` | string(64) | FK `tenants.id`, index | |
| `name` | string(200) | | |
| `email` | string(255) | nullable, index | Considerado PII; en la consola admin se muestra enmascarado |
| `company` | string(200) | nullable | |
| `plan` | string(50) | nullable | |
| `user_id` | int | FK `users.id`, nullable, unique, index | Cuenta de portal vinculada |
| `created_at` | datetime (tz) | default now(UTC) | |

Índice compuesto: `(tenant_id, email)`.

---

## `tickets`

Tickets de soporte por tenant.

| Columna | Tipo | Restricciones | Notas |
| --- | --- | --- | --- |
| `id` | int | PK | |
| `tenant_id` | string(64) | index | Filtro de aislamiento por tenant |
| `customer_id` | int | FK `customers.id`, nullable, index | Cliente del portal que originó el ticket |
| `subject` | text | **cifrado** | |
| `description` | text | **cifrado**, carga diferida | No se incluye en listados |
| `category` | string(100) | nullable, index | |
| `priority` | string(20) | nullable, index | `low` \| `medium` \| `high` \| `urgent` |
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
- `classification`: `{ category, suggested_priority }`
- `summary`: `{ summary, missing_information }`
- `reply`: `{ suggested_reply, sources, policy_flags }`

La columna `output` de la sugerencia puede actualizarse con el `edited_output` del feedback (`accepted`/`edited`).

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

## `tags` / `ticket_tags`

Tags por tenant y su asociación many-to-many con tickets (feature 017/023).

**`tags`**
| Columna | Tipo | Restricciones | Notas |
| --- | --- | --- | --- |
| `id` | int | PK | |
| `tenant_id` | string(64) | FK `tenants.id`, index | |
| `name` | string(50) | index | |
| `created_at` | datetime (tz) | default now(UTC) | |

Índice único compuesto: `(tenant_id, name)`.

**`ticket_tags`** — `id` PK; `ticket_id` FK `tickets.id` (CASCADE); `tag_id` FK `tags.id` (CASCADE). Índice único `(ticket_id, tag_id)`.

---

## Knowledge Base — `kb_*`

Artículos de base de conocimiento por tenant, versionado y tags relacionales.

**`kb_articles`**
| Columna | Tipo | Restricciones | Notas |
| --- | --- | --- | --- |
| `id` | int | PK | |
| `tenant_id` | string(64) | index | |
| `title` | string(200) | | |
| `body` | text | | |
| `category` | string(100) | nullable, index | |
| `status` | string(20) | default `"draft"`, index | `draft` \| `published` \| `archived` |
| `author_id` | int | FK `users.id` | |
| `current_version` | int | default `1` | |
| `created_at` / `updated_at` | datetime (tz) | defaults | |
| `published_at` | datetime (tz) | nullable | |

**`kb_article_versions`** — snapshot de cada edición (`article_id`, `version`, `title`, `body`, `category`, `author_id`, `change_note`, `created_at`).

**`kb_article_tags`** — `article_id` FK `kb_articles.id` (CASCADE), `tag_id` FK `tags.id` (CASCADE); índice único `(article_id, tag_id)`.

**`kb_categories`** — categorías gestionables por tenant (`id`, `tenant_id` FK, `name`, `created_at`); índice único `(tenant_id, name)`.

---

## Relaciones

```
Tenant 1──N Ticket | 1──N Customer | 1──N KbArticle | 1──N KbCategory | 1──N Tag
User 1──N RefreshToken | 1──N TicketMessage (author) | 1──N Ticket (assignee)
User N──N Tenant  (vía UserTenant: user_id, tenant_id, role)
User 1──1 Customer (customer del portal; customers.user_id)
Customer 1──N Ticket (tickets.customer_id)

Tenant (1) ──N Ticket
Ticket 1──N TicketMessage
Ticket 1──N AISuggestion
AISuggestion 1──1 Feedback
Ticket N──N Tag (vía ticket_tags)
KbArticle N──N Tag (vía kb_article_tags)

User 1──N AuditEvent
TenantPolicy (1 por tenant)
GlobalPolicy (1 fila global)
```
