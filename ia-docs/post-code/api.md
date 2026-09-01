# API Reference — Auto Help Desk Backend

Documentación para el agente de frontend. Base URL por defecto: `http://localhost:8000`.

## Autenticación

Los endpoints protegidos requieren el header `Authorization: Bearer <access_token>`.
**Excepciones** (sin bearer):
- `GET /health`
- `POST /auth/register`, `POST /auth/login`
- `GET /v1/tenants/public`
- `POST /auth/refresh` y `POST /auth/logout` (se autentican con el `refresh_token` del body)

El `access_token` expira en **15 min** (`expires_in` en segundos). Para renovarlo usa
`POST /auth/refresh` con el `refresh_token` (vigencia 30 días). Los claims del JWT incluyen
`sub` (user id), `tenant_id` (opcional, cuando el usuario seleccionó un tenant activo), `roles` y `type` (`access` | `refresh`).

### Roles y permisos

| Rol | Permisos |
| --- | --- |
| `agent` | tickets:read, ai:suggest, responses:edit, responses:send, kb:read |
| `supervisor` | + audit:view, kb:edit, kb:publish |
| `tenant_admin` | + tenant:configure |
| `platform_admin` | + ai_policies:manage |
| `customer` | persona:tickets (solo portal de personas `/v1/me/*`) |

- `platform_admin` puede no tener `tenant_id` (opera multi-tenant). Los roles `agent/supervisor/tenant_admin/customer` siempre están vinculados a uno o más tenants.
- Endpoints que requieren tenant (`/v1/tickets`, `/v1/workspace/my-tickets`, `/admin/*`) devuelven **403** si el usuario no tiene tenant.
- El alcance de tenant sale del JWT (`get_effective_tenant_ids`): tenant activo si el token trae `tenant_id`, o **todos** los tenants del usuario vía `user_tenants` si salteó la selección (`POST /auth/clear-tenant`).
- Los datos siempre se filtran por el alcance del usuario autenticado, nunca por inputs del cliente.

---

## Health

### `GET /health`
Check de salud del servicio.

- **Respuesta 200:**
  ```json
  { "status": "ok", "version": "0.1.1" }
  ```

---

## Auth — `/auth`

### `POST /auth/register`
Registro público. Roles permitidos: `agent`, `supervisor` y `customer`.

**Body:**
```json
{
  "name": "Juan Pérez",
  "email": "juan@example.com",
  "password": "claveSegura123",
  "role": "agent",
  "tenant_ids": ["tenant-abc"]
}
```

- `name` (1–255) y `password` (8–128) obligatorios. `tenant_ids` (o `tenant_id` legacy) opcional.
- **201** → `UserOut`. El rol `customer` además crea su perfil en `customers`.
- **403** → rol no permitido en registro público
- **404** → tenant inexistente
- **409** → email ya registrado

### `POST /auth/login`
**Body:**
```json
{ "email": "juan@example.com", "password": "claveSegura123", "tenant_id": "tenant-abc" }
```

- `tenant_id` opcional: si se envía, el token queda scopeado a ese tenant (403 si el usuario no pertenece).
- **200** → `TokenResponse`
- **401** → credenciales inválidas
- **403** → usuario inactivo / sin pertenencia al `tenant_id`

### `POST /auth/refresh`
Rota el par de tokens: revoca el refresh usado y emite uno nuevo (mantiene el `tenant_id` del token previo). Sin bearer.

**Body:**
```json
{ "refresh_token": "eyJ..." }
```

- **200** → `TokenResponse`
- **401** → refresh expirado, inválido o revocado

### `POST /auth/logout`
Revoca el refresh token. Sin bearer (usa el `refresh_token` del body).

**Body:**
```json
{ "refresh_token": "eyJ..." }
```

- **204** → sin contenido
- **401** → refresh inválido

### `GET /auth/me`
Datos del usuario autenticado (incluye `name` y `tenants`).

- **200** → `UserOut`
- **401** → sin token / token inválido o expirado

### `POST /auth/switch-tenant`
Cambia al tenant activo y emite tokens scopeados a él. El usuario debe pertenecer.

**Body:** `{ "tenant_id": "tenant-abc" }`

- **200** → `TokenResponse`
- **403** → no pertenece al tenant
- **404** → tenant inexistente

### `GET /auth/tenants`
Lista los tenants a los que pertenece el usuario autenticado.

- **200** → `[TenantInfo]` (`{id, name, slug, role}`)

### `POST /auth/clear-tenant`
Emite tokens sin `tenant_id`: el usuario opera sobre **todos** sus tenants.

- **200** → `TokenResponse`

---

## Tickets — `/v1/tickets`

Requieren tenant. Devuelven **403** "Rol sin tenant asignado" si el usuario no tiene tenant y **404** si el ticket es inexistente o de otro tenant.

### `GET /v1/tickets/categories`
Categorías válidas predefinidas.

- **200** → `[{ "id": "billing", "label": "Facturación", ... }]` (constante `TICKET_CATEGORIES`)

### `POST /v1/tickets`
Crea un ticket (estado inicial `open`). Permiso: `tickets:read` o `responses:edit`.

**Body:**
```json
{
  "subject": "No puedo pagar con mi tarjeta",
  "description": "Intento el pago y sale error 4012.",
  "category": "billing",
  "priority": "high"
}
```

- `subject` (1–200) y `description` obligatorios. `category` (≤100) y `priority` (`low|medium|high|urgent`) opcionales.
- **201** → `TicketOut`

### `GET /v1/tickets/{ticket_id}`
Detalle de un ticket (incluye `description` descifrada).

- **200** → `TicketOut`
- **404** → no encontrado / otro tenant

### `GET /v1/tickets`
Lista tickets del tenant (ordenados por `created_at` desc, sin `description`).

**Query params (todos opcionales):**
| Param | Tipo | Restricción |
| --- | --- | --- |
| `status` | string | `open\|in_progress\|on_hold\|closed` |
| `category` | string | ≤100 chars |
| `priority` | string | `low\|medium\|high\|urgent` |
| `assignee_id` | int | — |
| `date_from` | datetime | ISO 8601 |
| `date_to` | datetime | ISO 8601 |
| `q` | string | ≤100; filtra por categoría o tag (`category.ilike` / tag name) |
| `limit` | int | 1–200, default 50 |
| `offset` | int | ≥0, default 0 |

- **200** → `TicketListOut`

### `PATCH /v1/tickets/{ticket_id}`
Actualiza campos del ticket. Permiso: `responses:edit` **y** `responses:send`.

**Body (al menos un campo):**
```json
{ "status": "in_progress", "priority": "urgent", "category": "billing", "assignee_id": 42 }
```

- **Reglas de asignación (`assignee_id`)**: el rol `agent` solo puede asignarse a sí mismo o desasignar (`null`) → 403 si asigna a otro; `supervisor`/`tenant_admin`/`platform_admin` pueden asignar a cualquier **agente activo del tenant del ticket** → 404 si no existe o no es agente del tenant.
- **200** → `TicketOut`
- **404** → no encontrado
- **422** → body vacío ("Sin cambios") o campos inválidos

### `POST /v1/tickets/{ticket_id}/messages`
Agrega un mensaje al ticket. Permiso: `responses:edit`.

**Body:**
```json
{ "body": "El cliente dice que ya reintentó 3 veces." }
```

- `author_id` se toma del usuario autenticado.
- **201** → `TicketMessageOut`
- **404** → ticket no encontrado
- **422** → ticket cerrado ("No se pueden enviar mensajes a un ticket cerrado.")

### `GET /v1/tickets/{ticket_id}/messages`
Mensajes del ticket (ordenados por `created_at` asc).

- **200** → `[TicketMessageOut]`
- **404** → ticket no encontrado

### `GET /v1/tickets/{ticket_id}/tags`
Tags asociadas al ticket.

- **200** → `[TicketTagOut]` (`{ticket_id, tag_id, tag}`)

### `POST /v1/tickets/{ticket_id}/tags`
Agrega una tag al ticket (body `{ "tag_id": 1 }`). Permiso: `responses:edit`.

- **201** → `TicketTagOut`
- **404** → ticket o tag inexistente
- **409** → tag ya asociada al ticket

### `DELETE /v1/tickets/{ticket_id}/tags/{tag_id}`
Quita una tag del ticket. Permiso: `responses:edit`.

- **204** → sin contenido
- **404** → no encontrada

### `POST /v1/tickets/{ticket_id}/close`
Cierra el ticket (estado `closed`). Permiso: `responses:send`.

- **200** → `TicketOut`
- **404** → no encontrado

---

## Tags — `/v1/tags`

### `GET /v1/tags`
Lista/busca tags del tenant (`search` opcional por subcadena, máx 50). Permiso: `tickets:read`.

- **200** → `[TagOut]`

### `POST /v1/tags`
Crea una tag para el tenant. Permiso: `responses:edit`.

**Body:** `{ "name": "reembolso" }`

- **201** → `TagOut`
- **409** → ya existe una tag con ese nombre (case-insensitive)
- **422** → nombre vacío

---

## Agents — `/v1/agents`

### `GET /v1/agents`
Agentes activos de los tenants efectivos (selector de asignación). Permiso: `tickets:read`.

- **200** → `[AgentOut]` (`{id, name, email, role, is_active}`)

---

## Customers — `/v1/customers`

Requieren `tickets:read`. **Atención:** devuelven el `email` crudo (uso operativo). Para la consola admin sin PII usar `GET /admin/customers`.

### `GET /v1/customers`
- `limit` (1–200), `offset`. **200** → `[CustomerOut]`

### `GET /v1/customers/{customer_id}`
- **200** → `CustomerOut` · **404** → no encontrado / otro tenant

`CustomerOut`: `{id, tenant_id, name, email, company, plan, created_at}`

---

## Admin — `/admin`

Requieren `CONFIGURE_TENANT` (`tenant_admin` / `platform_admin`). Las políticas globales requieren `MANAGE_AI_POLICIES` (`platform_admin`).

### `GET /admin/users`
Lista usuarios del/los tenant(s) efectivos, excluyendo clientes (`role != customer`).

**Query params:** `limit` (1–200, default 50), `offset` (≥0), `q` (nombre o email `ilike`), `role` (`tenant_admin|supervisor|agent|platform_admin`).

- **200** → `UserListOut` (`{items: [UserOut], total, limit, offset}`)
- **403** → rol sin tenant

### `POST /admin/users`
Crea un usuario. Un `tenant_admin` solo en su propio tenant y con roles `tenant_admin|supervisor|agent`; un `platform_admin` puede asignar cualquier rol y tenant.

**Body:**
```json
{ "name": "Nuevo", "email": "nuevo@example.com", "password": "claveSegura123", "role": "agent", "tenant_id": "tenant-abc" }
```

- `name` obligatorio; `password` 8–128. `tenant_id` **obligatorio** para `platform_admin`.
- **201** → `UserOut`
- **403** → rol fuera del alcance / otro tenant
- **409** → email ya registrado
- **422** → falta `tenant_id`

### `PATCH /admin/users/{user_id}`
Actualiza rol, activación o nombre. Un `tenant_admin` no puede asignar `platform_admin` ni desactivarse a sí mismo.

**Body:** `{ "role": "supervisor", "is_active": false, "name": "Nuevo Nombre" }`

- **200** → `UserOut`
- **403** → desactivarse a sí mismo / rol fuera del alcance
- **404** → usuario no encontrado
- **422** → body vacío (debe indicar `role`, `is_active` o `name`)

### `GET /admin/customers`
Clientes del/los tenant(s) con **PII enmascarada** (email nunca crudo).

**Query params:** `limit`, `offset`, `q` (nombre o empresa `ilike`), `tenant_id` (opcional; valida pertenencia del usuario → 403 si no es miembro).

- **200** → `CustomerListOut` (`{items: [CustomerAdminOut], total, limit, offset}`) donde `CustomerAdminOut` = `{id, tenant_id, name, email_masked, company, plan, created_at}`
- **403** → rol sin tenant / `tenant_id` ajeno

### `GET /admin/ai-policy`
Política IA del tenant (si no existe devuelve default `ai_enabled: true`).

- **200** → `TenantPolicyOut`
- **403** → rol sin tenant

### `PUT /admin/ai-policy`
Actualiza la política IA del tenant.

**Body:**
```json
{
  "ai_enabled": true,
  "tone": "profesional",
  "language": "es",
  "allowed_categories": ["billing", "technical"],
  "escalation_rules": { "urgent": "supervisor" }
}
```

Todos los campos opcionales (`ai_enabled` default `true`). `tone` ≤50 chars, `language` ≤10.

- **200** → `TenantPolicyOut`

### `GET /admin/ai-policies/global`
Política global efectiva (usa defaults de `.env` si no hay override). Permiso: `ai_policies:manage`.

- **200** → `GlobalPolicyOut`

### `PUT /admin/ai-policies/global`
Actualiza overrides globales. Solo persiste los campos enviados; los demás usan default. Permiso: `ai_policies:manage`.

**Body:**
```json
{
  "llm_model": "gpt-4o-mini",
  "ai_confidence_threshold": 0.7,
  "guardrails_enabled": true,
  "llm_rate_max_calls": 60
}
```

- `ai_confidence_threshold`: 0.0–1.0. `llm_rate_max_calls`: ≥1.
- **200** → `GlobalPolicyOut`

---

## IA — `/v1/ai`

Requieren `ai:suggest`. Los endpoints de clasificación/resumen/respuesta/ping/analyze pueden devolver:
- **403** → IA deshabilitada para este tenant (`TenantPolicy.ai_enabled=false`)
- **422** → contenido bloqueado por política de seguridad (guardrails) o salida inválida del LLM
- **429** → límite de rate del LLM excedido
- **503** → IA deshabilitada globalmente (`AI_FEATURES_ENABLED=false`) o LLM no disponible
- **404** → ticket no encontrado / de otro tenant

### `POST /v1/ai/ping`
Prueba de conectividad del LLM.

- **200** → `LLMPingInfo`

### `GET /v1/ai/info`
Config del orquestador sin secretos. Permiso: `audit:view`.

- **200:**
  ```json
  {
    "provider": "mock",
    "model": "gpt-4o-mini",
    "rate_max_calls": 60,
    "rate_window_seconds": 60,
    "max_retries": 2
  }
  ```

### `POST /v1/ai/tickets/{ticket_id}/classify`
Clasifica el ticket (categoría y prioridad sugerida). Persiste una `AISuggestion` (type=classification, state=draft).

- **200** → `ClassificationOut`

### `POST /v1/ai/tickets/{ticket_id}/summary`
Resume el ticket. Persiste una `AISuggestion` (type=summary).

- **200** → `SummaryOut`

### `POST /v1/ai/tickets/{ticket_id}/suggested-reply`
Sugiere una respuesta editable. Body opcional para ajustar tono/idioma.

**Body (opcional):**
```json
{ "tone": "empático", "language": "es" }
```

- **200** → `SuggestedReplyOut`

### `POST /v1/ai/tickets/{ticket_id}/analyze`
Ejecuta classify + summary + suggested-reply en paralelo y agrega recomendaciones de KB, detección de PII y riesgos.

- **200** → `AnalyzeOut`:
  ```json
  {
    "classification": { },
    "summary": { },
    "suggested_reply": { },
    "kb_recommendations": [ { "article_id": 1, "title": "...", "score": 0.8 } ],
    "pii_detected": [ { "type": "email", "value": "...", "position": 12 } ],
    "risks": [ "..." ]
  }
  ```

---

## Feedback y sugerencias

### `POST /v1/ai/tickets/{ticket_id}/feedback`
Registra la decisión del agente sobre una sugerencia IA (actualiza su `state`). Permiso: `responses:edit`.

**Body:**
```json
{
  "suggestion_id": 12,
  "action": "accepted",
  "reason": "Respuesta clara",
  "edited_content_hash": "sha256:...",
  "edited_output": { "category": "billing", "priority": "high" }
}
```

- `action` (`accepted|edited|rejected|flagged`). `reason`, `edited_content_hash` y `edited_output` (persistido en la sugerencia) opcionales.
- **200** → `FeedbackOut`
- **404** → ticket o sugerencia no encontrada / de otro tenant

### `GET /v1/ai/tickets/{ticket_id}/suggestions`
Lista sugerencias IA de un ticket del tenant (ordenadas por `created_at` desc). Permiso: `tickets:read`.

- **200** → `[SuggestionOut]`
- **404** → ticket no encontrado

### `GET /v1/workspace/my-tickets`
Bandeja del agente: tickets asignados a él.

**Query params:** `status` (`open|in_progress|on_hold|closed`), `q` (≤100), `limit` (1–200, default 50), `offset`.

- **200** → `TicketListOut`

---

## Portal de personas — `/v1/me`

Requieren permiso `persona:tickets` (rol `customer`). Aislamiento por `customers.user_id` + tenant.

### `GET /v1/me` — perfil del cliente `{id, name, email, company, tenant_id, tenant_name}`

### `GET /v1/me/tickets` — mis tickets (filtros `status`/`category`/`priority`/`q` + paginado) → `TicketListOut`

### `POST /v1/me/tickets` — crea mi ticket (asociado al customer) → 201 `TicketOut`

### `GET /v1/me/tickets/{ticket_id}` — detalle de mi ticket → `TicketOut` · 404 si no es mío

### `GET /v1/me/tickets/{ticket_id}/messages` → `[TicketMessageOut]`

### `POST /v1/me/tickets/{ticket_id}/messages` — envío manual (sin LLM). 422 si el ticket está `closed`.

---

## Tenants — `/v1/tenants`

### `GET /v1/tenants/public`
Lista tenants habilitados (id, nombre, slug) para el registro. **Sin autenticación.**

- **200** → `[TenantOut]`

### `GET /v1/tenants`
Lista todos los tenants. Permiso: `audit:view` (platform_admin / supervisor).

- **200** → `[TenantOut]`

### `GET /v1/tenants/{tenant_id}`
Detalle de un tenant. Permiso: `audit:view`.

- **200** → `TenantOut` · **404** → no encontrado

---

## Knowledge Base — `/v1/kb`

Requieren `kb:read`; operaciones de escritura requieren `kb:edit`/`kb:publish`.

### `GET /v1/kb/categories` — categorías del tenant (siembra defaults la primera vez) → `[KbCategoryOut]`
### `POST /v1/kb/categories` — crea categoría (`kb:edit`) → 201 · 409 si ya existe
### `DELETE /v1/kb/categories/{category_id}` — elimina categoría (`kb:edit`) → 204

### `GET /v1/kb/articles` — filtros `status` (`draft|published|archived`), `category`, `tag`, `search` + paginado → `KbArticleListOut`
### `POST /v1/kb/articles` — crea artículo (`kb:edit`) → 201 `KbArticleOut`
### `GET /v1/kb/articles/{article_id}` → `KbArticleOut` · 404
### `PATCH /v1/kb/articles/{article_id}` — edita (crea nueva versión) (`kb:edit`) → `KbArticleOut`
### `POST /v1/kb/articles/{article_id}/publish` — publica (`kb:publish`) → `KbArticleOut`
### `POST /v1/kb/articles/{article_id}/archive` — archiva (`kb:edit`) → `KbArticleOut`
### `POST /v1/kb/articles/{article_id}/restore` — restaura (`kb:edit`) → `KbArticleOut`
### `GET /v1/kb/articles/{article_id}/versions` — historial de versiones → `[KbArticleVersionOut]`

`KbArticleOut`: `{id, tenant_id, title, body, category, tags: [str], status, author_id, author_name, current_version, created_at, updated_at, published_at}`

---

## PII — `/v1/pii`

### `POST /v1/pii/redact`
Redacta PII de un texto. Permiso: `ai:suggest`.

**Body:**
```json
{ "text": "Contacte al cliente Juan Pérez al 555-1234", "mode": "redact" }
```

- `mode` (`off|detect|redact`, default `redact`). Los reemplazos usan tokens `[[PII:email:hash8]]` (no revelan el valor original).
- **200** → `PIIRedactResponse` · **422** → modo inválido

---

## Auditoría — `/audit`

### `GET /audit/events`
Lista eventos de auditoría del tenant (append-only), ordenados por `created_at` desc. Permiso: `audit:view`.

**Query params (todos opcionales):** `action`, `service`, `user_id`, `result`, `date_from`, `date_to`, `limit` (1–200, default 50), `offset`.

- **200** → `[AuditEventOut]`
- **403** → rol sin tenant

---

## Métricas — `/v1/metrics`

### `GET /v1/metrics`
Métricas en formato texto Prometheus. Permiso: `audit:view`.

- **200** → `text/plain`

---

## Schemas de respuesta

### `UserOut`
```json
{
  "id": 1,
  "email": "juan@example.com",
  "name": "Juan Pérez",
  "role": "agent",
  "tenant_id": "tenant-abc",
  "is_active": true,
  "created_at": "2026-08-11T10:00:00Z",
  "tenants": [ { "id": "tenant-abc", "name": "Acme", "slug": "acme", "role": "agent" } ]
}
```

### `TokenResponse`
```json
{ "access_token": "eyJ...", "refresh_token": "eyJ...", "token_type": "bearer", "expires_in": 900 }
```

### `TicketOut`
```json
{
  "id": 1,
  "tenant_id": "tenant-abc",
  "subject": "No puedo pagar",
  "description": "Intento el pago y sale error.",
  "category": "billing",
  "priority": "high",
  "status": "open",
  "customer_id": null,
  "assignee_id": null,
  "assignee": { "id": 5, "name": "Agente", "email": "agente@example.com", "role": "agent" },
  "created_at": "2026-08-11T10:00:00Z",
  "updated_at": "2026-08-11T10:00:00Z"
}
```

### `TicketSummaryOut` (ítem de listas)
Igual que `TicketOut` **sin** `description`.

### `TicketListOut`
```json
{ "items": [ { /* TicketSummaryOut */ } ], "total": 7, "limit": 50, "offset": 0 }
```

### `TicketMessageOut`
```json
{ "id": 1, "ticket_id": 5, "author_id": 3, "author_name": "Agente", "body": "texto", "created_at": "2026-08-11T10:00:00Z" }
```

### `ClassificationOut`
```json
{
  "category": "billing",
  "suggested_priority": "high",
  "confidence": 0.92,
  "warnings": [],
  "suggestion_id": 12,
  "trace_id": "uuid"
}
```

### `SummaryOut`
```json
{
  "summary": "El cliente no puede pagar con tarjeta.",
  "missing_information": null,
  "confidence": 0.9,
  "warnings": [],
  "suggestion_id": 13,
  "trace_id": "uuid"
}
```

### `SuggestedReplyOut`
```json
{
  "suggested_reply": "Hola, lamentamos el inconveniente...",
  "confidence": 0.88,
  "sources": ["ticket #5"],
  "policy_flags": [],
  "warnings": [],
  "suggestion_id": 14,
  "trace_id": "uuid"
}
```

### `FeedbackOut`
```json
{
  "suggestion_id": 12,
  "action": "accepted",
  "reason": "Respuesta clara",
  "edited_content_hash": null,
  "created_at": "2026-08-11T10:05:00Z"
}
```

### `SuggestionOut`
```json
{
  "id": 12,
  "type": "classification",
  "state": "draft",
  "confidence": 0.92,
  "model": "gpt-4o-mini",
  "prompt_version": "v1",
  "output": { "category": "billing", "suggested_priority": "high" },
  "created_at": "2026-08-11T10:00:00Z"
}
```

`type`: `classification` | `summary` | `reply`. `state`: `draft` | `accepted` | `edited` | `rejected` | `flagged`. `output` es la salida estructurada (sin PII) según el tipo.

### `TenantPolicyOut`
```json
{
  "tenant_id": "tenant-abc",
  "ai_enabled": true,
  "tone": "profesional",
  "language": "es",
  "allowed_categories": ["billing", "technical"],
  "escalation_rules": { "urgent": "supervisor" },
  "updated_at": "2026-08-11T10:00:00Z"
}
```

### `GlobalPolicyOut`
```json
{
  "llm_model": "gpt-4o-mini",
  "ai_confidence_threshold": 0.6,
  "guardrails_enabled": true,
  "llm_rate_max_calls": 60
}
```

### `LLMPingInfo`
```json
{ "ok": true, "model": "gpt-4o-mini", "trace_id": "uuid" }
```

### `PIIRedactResponse`
```json
{ "text": "Contacte al cliente [[PII:name:abc123]] al [[PII:phone:def456]]", "report": { "types": { "name": 1, "phone": 1 }, "total": 2 } }
```

### `AuditEventOut`
```json
{
  "id": 1,
  "created_at": "2026-08-11T10:00:00Z",
  "tenant_id": "tenant-abc",
  "user_id": 3,
  "action": "ticket.created",
  "service": "tickets",
  "model": "Ticket",
  "model_version": null,
  "prompt_version": null,
  "trace_id": "uuid",
  "result": "success",
  "confidence": null,
  "detail": { "ticket_id": 5 }
}
```

---

## Errores comunes

El formato de error es FastAPI estándar: `{ "detail": "mensaje" }`.

| Código | Significado |
| --- | --- |
| 401 | Token ausente, inválido o expirado |
| 403 | Permiso insuficiente / sin tenant / IA deshabilitada para el tenant |
| 404 | Recurso no encontrado o de otro tenant |
| 409 | Email ya registrado / tag duplicada |
| 422 | Validación del body/query falló / ticket cerrado |
| 429 | Rate limit del LLM excedido |
| 503 | IA deshabilitada globalmente / LLM no disponible |