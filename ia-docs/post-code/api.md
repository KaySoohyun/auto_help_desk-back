# API Reference — Auto Help Desk Backend

Documentación para el agente de frontend. Base URL por defecto: `http://localhost:8000`.

## Autenticación

Todos los endpoints excepto `/health`, `POST /auth/register` y `POST /auth/login` requieren
el header `Authorization: Bearer <access_token>`.

El `access_token` expira en **15 min** (`expires_in` en segundos). Para renovarlo usa
`POST /auth/refresh` con el `refresh_token` (vigencia 30 días). Los claims del JWT incluyen
`sub` (user id), `tenant_id`, `roles` y `type` (`access` | `refresh`).

### Roles y permisos

| Rol | Permisos |
| --- | --- |
| `agent` | tickets:read, ai:suggest, responses:edit, responses:send |
| `supervisor` | + audit:view |
| `tenant_admin` | + tenant:configure |
| `platform_admin` | + ai_policies:manage |

- `platform_admin` y `tenant_admin` pueden no tener `tenant_id` (el `platform_admin` opera multi-tenant).
- Endpoints que requieren tenant (`/v1/tickets`, `/v1/workspace/my-tickets`, `/admin/*`) devuelven **403** si el usuario no tiene tenant.
- Los datos siempre se filtran por el tenant del usuario autenticado, nunca por inputs del cliente.

---

## Health

### `GET /health`
Check de salud del servicio.

- **Respuesta 200:**
  ```json
  { "status": "ok", "version": "0.1.0" }
  ```

---

## Auth — `/auth`

### `POST /auth/register`
Registro público. Solo roles `agent` y `supervisor`.

**Body:**
```json
{
  "email": "agente@example.com",
  "password": "claveSegura123",
  "role": "agent",
  "tenant_id": "tenant-abc"        // opcional
}
```

- `password`: 8–128 caracteres.
- **201** → `UserOut`
- **403** → rol no permitido en registro público
- **409** → email ya registrado

### `POST /auth/login`
**Body:**
```json
{ "email": "agente@example.com", "password": "claveSegura123" }
```

- **200** → `TokenResponse`
- **401** → credenciales inválidas
- **403** → usuario inactivo

### `POST /auth/refresh`
Rota el par de tokens: revoca el refresh usado y emite uno nuevo.

**Body:**
```json
{ "refresh_token": "eyJ..." }
```

- **200** → `TokenResponse`
- **401** → refresh expirado, inválido o revocado

### `POST /auth/logout`
Revoca el refresh token. **Requiere auth.**

**Body:**
```json
{ "refresh_token": "eyJ..." }
```

- **204** → sin contenido
- **401** → refresh inválido

### `GET /auth/me`
Datos del usuario autenticado.

- **200** → `UserOut`
- **401** → sin token / token inválido o expirado

---

## Tickets — `/v1/tickets`

Requieren tenant. Devuelven **403** "Rol sin tenant asignado" si el usuario no tiene tenant y **404** si el ticket es inexistente o de otro tenant.

### `POST /v1/tickets`
Crea un ticket (estado inicial `open`). Permiso: `tickets:read` o `responses:edit`.

**Body:**
```json
{
  "subject": "No puedo pagar con mi tarjeta",
  "description": "Intento el pago y sale error 4012.",
  "category": "billing",
  "priority": "high",
  "language": "es"
}
```

- `subject`: 1–200 chars. `description`: obligatoria. `category`: ≤100 chars.
- `priority` (`low|medium|high|urgent`), `category` y `language` (default `"es"`) opcionales.
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
| `limit` | int | 1–200, default 50 |
| `offset` | int | ≥0, default 0 |

- **200** → `TicketListOut`

### `PATCH /v1/tickets/{ticket_id}`
Actualiza campos del ticket. Permiso: `responses:edit` o `responses:send`.

**Body (al menos un campo):**
```json
{ "status": "in_progress", "priority": "urgent", "category": "billing", "assignee_id": 42 }
```

- **200** → `TicketOut`
- **404** → no encontrado
- **422** → body vacío ("Sin cambios")

### `POST /v1/tickets/{ticket_id}/messages`
Agrega un mensaje al ticket. Permiso: `responses:edit`.

**Body:**
```json
{ "body": "El cliente dice que ya reintentó 3 veces." }
```

- `author_id` se toma del usuario autenticado.
- **201** → `TicketMessageOut`
- **404** → ticket no encontrado

### `GET /v1/tickets/{ticket_id}/messages`
Mensajes del ticket (ordenados por `created_at` asc).

- **200** → `[TicketMessageOut]`
- **404** → ticket no encontrado

### `POST /v1/tickets/{ticket_id}/close`
Cierra el ticket (estado `closed`). Permiso: `responses:send`.

- **200** → `TicketOut`
- **404** → no encontrado

---

## Admin — `/admin`

Requieren `CONFIGURE_TENANT` (`tenant_admin` / `platform_admin`). La gestión de políticas globales requiere `MANAGE_AI_POLICIES` (`platform_admin`).

### `GET /admin/users`
Lista usuarios del tenant del autenticado.

**Query params:** `limit` (1–200, default 50), `offset` (≥0).

- **200** → `[UserOut]`
- **403** → rol sin tenant

### `POST /admin/users`
Crea un usuario. Un `tenant_admin` solo en su propio tenant y con roles `tenant_admin|supervisor|agent`; un `platform_admin` puede asignar cualquier rol y tenant.

**Body:**
```json
{ "email": "nuevo@example.com", "password": "claveSegura123", "role": "agent", "tenant_id": "tenant-abc" }
```

- `password`: 8–128. `tenant_id` **obligatorio** para `platform_admin`.
- **201** → `UserOut`
- **403** → rol fuera del alcance / otro tenant
- **409** → email ya registrado
- **422** → falta `tenant_id`

### `PATCH /admin/users/{user_id}`
Actualiza rol o activación. Un `tenant_admin` no puede asignar `platform_admin` ni desactivarse a sí mismo.

**Body:**
```json
{ "role": "supervisor", "is_active": false }
```

- **200** → `UserOut`
- **403** → desactivarse a sí mismo / rol fuera del alcance
- **404** → usuario no encontrado
- **422** → sin `role` ni `is_active`

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

Requieren `ai:suggest`. Los endpoints de clasificación/resumen/respuesta/ping pueden devolver:
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
Clasifica el ticket (categoría, intención, prioridad sugerida). Persiste una `AISuggestion` (type=classification, state=draft).

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

---

## Workspace — `/v1`

### `POST /v1/ai/tickets/{ticket_id}/feedback`
Registra la decisión del agente sobre una sugerencia IA (actualiza su `state`). Permiso: `responses:edit`.

**Body:**
```json
{
  "suggestion_id": 12,
  "action": "accepted",
  "reason": "Respuesta clara",
  "edited_content_hash": "sha256:..."
}
```

- `action` (`accepted|edited|rejected|flagged`). `reason` y `edited_content_hash` opcionales.
- **200** → `FeedbackOut`
- **404** → ticket o sugerencia no encontrada / de otro tenant

### `GET /v1/ai/tickets/{ticket_id}/suggestions`
Lista sugerencias IA de un ticket del tenant (ordenadas por `created_at` desc). Permiso: `tickets:read`.

- **200** → `[SuggestionOut]`
- **404** → ticket no encontrado

### `GET /v1/workspace/my-tickets`
Bandeja del agente: tickets asignados a él.

**Query params:** `status` (`open|in_progress|on_hold|closed`), `limit` (1–200, default 50), `offset`.

- **200** → `TicketListOut`

---

## PII — `/v1/pii`

### `POST /v1/pii/redact`
Redacta PII de un texto. Permiso: `ai:suggest`.

**Body:**
```json
{ "text": "Contacte al cliente Juan Pérez al 555-1234", "mode": "redact" }
```

- `mode` (`off|detect|redact`, default `redact`).
- **200** → `PIIRedactResponse`
- **422** → modo inválido

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
  "email": "agente@example.com",
  "role": "agent",
  "tenant_id": "tenant-abc",
  "is_active": true,
  "created_at": "2026-08-11T10:00:00Z"
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
  "language": "es",
  "status": "open",
  "assignee_id": null,
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
{ "id": 1, "ticket_id": 5, "author_id": 3, "body": "texto", "created_at": "2026-08-11T10:00:00Z" }
```

### `ClassificationOut`
```json
{
  "category": "billing",
  "subcategory": "tarjeta",
  "intent": "incident",
  "suggested_priority": "high",
  "confidence": 0.92,
  "rationale": "Error de pago recurrente",
  "warnings": [],
  "suggestion_id": 12,
  "trace_id": "uuid"
}
```

### `SummaryOut`
```json
{
  "summary": "El cliente no puede pagar con tarjeta.",
  "missing_information": "Últimos 4 dígitos de la tarjeta",
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
  "output": { "category": "billing", "...": "..." },
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
{ "text": "Contacte al cliente [NOMBRE] al [TELÉFONO]", "report": { "types": { "name": 1, "phone": 1 }, "total": 2 } }
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
| 409 | Email ya registrado |
| 422 | Validación del body/query falló |
| 429 | Rate limit del LLM excedido |
| 503 | IA deshabilitada globalmente / LLM no disponible |
