# Feature 020 — Rediseño del detalle de ticket (Backend)

## Contexto

El frontend requiere rediseñar el detalle de ticket a 3 columnas. Para ello se necesitan:
1. Nuevos modelos de datos: `tenants`, `customers`, `user_tenants`, `ticket_tags`, `article_tags`
2. Migración de `users.tenant_id` a relación many-to-many (`user_tenants`)
3. Migración de `kb_articles.tags` (JSON) a tabla relacional (`article_tags`)
4. Nuevo endpoint LLM unificado que ejecute classify + summary + suggested-reply en paralelo
5. Endpoints de tags, customers y tenants

## Objetivos

1. Soporte multi-tenant real: usuarios pueden pertenecer a múltiples tenants con roles distintos
2. Modelo de customers para datos de clientes
3. Tags relacionales para tickets y artículos (reemplaza JSON)
4. Endpoint `/analyze` que devuelve todo el análisis LLM en una sola llamada
5. Endpoints CRUD para tags, customers y tenants

## Alcance

### Nuevos modelos

#### `tenants`
| Columna | Tipo | Restricciones |
|---------|------|---------------|
| `id` | string(64) | PK |
| `name` | string(100) | not null |
| `slug` | string(100) | unique, not null |
| `created_at` | datetime(tz) | default now(UTC) |

#### `customers`
| Columna | Tipo | Restricciones |
|---------|------|---------------|
| `id` | int | PK |
| `tenant_id` | string(64) | FK tenants.id, index |
| `name` | string(200) | not null |
| `email` | string(255) | index |
| `company` | string(200) | nullable |
| `plan` | string(50) | nullable |
| `created_at` | datetime(tz) | default now(UTC) |

#### `user_tenants`
| Columna | Tipo | Restricciones |
|---------|------|---------------|
| `user_id` | int | FK users.id, PK |
| `tenant_id` | string(64) | FK tenants.id, PK |
| `role` | string(50) | not null |
| `created_at` | datetime(tz) | default now(UTC) |

#### `ticket_tags`
| Columna | Tipo | Restricciones |
|---------|------|---------------|
| `ticket_id` | int | FK tickets.id, PK |
| `tag_id` | int | FK tags.id, PK |

#### `article_tags`
| Columna | Tipo | Restricciones |
|---------|------|---------------|
| `article_id` | int | FK kb_articles.id, PK |
| `tag_id` | int | FK tags.id, PK |

### Cambios en modelos existentes

- **`users`**: eliminar `tenant_id` (migrar a `user_tenants`)
- **`tickets`**: agregar `customer_id` (FK nullable)
- **`kb_articles`**: eliminar `tags` (JSON), usar `article_tags`

### Nuevos endpoints

#### `POST /v1/ai/tickets/{id}/analyze`

Ejecuta en paralelo con `asyncio.gather`:
- `classify_service.classify(...)`
- `summarizer_service.summarize(...)`
- `reply_suggester_service.suggest(...)`

Adicionalmente:
- `kb_recommendations`: busca artículos publicados por categoría del ticket
- `pii_detected`: ejecuta `pii_redactor.redact()` sobre el contenido del ticket

Respuesta:
```json
{
  "classification": { ... },
  "summary": { ... },
  "suggested_reply": { ... },
  "kb_recommendations": [
    { "article_id": 5, "title": "...", "score": 0.95 }
  ],
  "pii_detected": [
    { "type": "email", "value": "[EMAIL]", "position": 45 }
  ],
  "risks": []
}
```

Permisos: `ai:suggest`. Errores: 403 (IA deshabilitada), 404 (ticket no encontrado), 422 (salida inválida), 429 (rate limit), 503 (IA no disponible).

#### Tags de tickets

- `GET /v1/tickets/{id}/tags` → `[TagOut]`
- `POST /v1/tickets/{id}/tags` body `{ "tag_id": 5 }` → 201
- `DELETE /v1/tickets/{id}/tags/{tag_id}` → 204

Permisos: `tickets:read` para GET, `responses:edit` para POST/DELETE.

#### Customers

- `GET /v1/customers` query `limit`, `offset` → `[CustomerOut]`
- `GET /v1/customers/{id}` → `CustomerOut`

Permisos: `tickets:read`.

#### Tenants

- `GET /v1/tenants` → `[TenantOut]` (solo `platform_admin`)
- `GET /v1/tenants/{id}` → `TenantOut` (solo `platform_admin` o miembro del tenant)

### Migraciones

1. Crear tabla `tenants`
2. Seed de tenants (usar `tenant_id` existentes en `users`)
3. Crear tabla `user_tenants`
4. Migrar datos: `INSERT INTO user_tenants (user_id, tenant_id, role) SELECT id, tenant_id, role FROM users WHERE tenant_id IS NOT NULL`
5. Eliminar columna `users.tenant_id`
6. Crear tabla `customers`
7. Agregar columna `tickets.customer_id`
8. Crear tablas `ticket_tags` y `article_tags`
9. Migrar `kb_articles.tags` (JSON) a `article_tags`
10. Eliminar columna `kb_articles.tags`

### Seed de prueba

- 2 tenants: "test-tenant" (slug: test-tenant), "acme-corp" (slug: acme-corp)
- 3 customers por tenant
- Tags de prueba por tenant
- Migrar usuarios existentes a `user_tenants`

## Fuera de alcance

- CRUD completo de tenants (solo lectura por ahora)
- CRUD completo de customers (solo lectura por ahora)
- Portal público de clientes
- Búsqueda semántica para KB recommendations

## Riesgos

- Migración de `users.tenant_id` puede romper código existente que accede a `user.tenant_id`
- Performance de `/analyze` si los calls al LLM son lentos (mitigado con paralelo)
- Migración de `kb_articles.tags` (JSON) puede perder datos si el JSON es inválido

## Tests

- Tests unitarios de modelos
- Tests de migraciones (round-trip)
- Tests de endpoints nuevos
- Tests de `/analyze` con mock LLM
- Tests de permisos (RBAC)
- Tests de aislamiento por tenant
