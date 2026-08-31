# Plan — Feature 020 Rediseño del detalle de ticket (Backend)

## Orden de implementación

### Paso 1: Modelos y migraciones

1. Crear modelo `Tenant` + tabla
2. Crear modelo `Customer` + tabla
3. Crear modelo `UserTenant` + tabla
4. Crear modelo `TicketTag` + tabla
5. Crear modelo `ArticleTag` + tabla
6. Script de migración: `users.tenant_id` → `user_tenants`
7. Script de migración: `kb_articles.tags` → `article_tags`
8. Agregar `customer_id` a `tickets`
9. Eliminar columnas obsoletas

### Paso 2: Schemas Pydantic

1. `TenantOut`, `TenantCreate`
2. `CustomerOut`, `CustomerCreate`, `CustomerUpdate`
3. `UserTenantOut`, `UserTenantCreate`
4. `TicketTagOut`, `ArticleTagOut`
5. `LlmAnalyzeOutput`, `KbRecommendation`, `PiiDetection`

### Paso 3: Repositorios

1. `TenantRepository`
2. `CustomerRepository`
3. `UserTenantRepository`
4. `TicketTagRepository`
5. `ArticleTagRepository`

### Paso 4: Servicios

1. `TenantService`
2. `CustomerService`
3. `AnalyzeService` (orquesta classify + summary + reply + KB + PII)

### Paso 5: Endpoints

1. `POST /v1/ai/tickets/{id}/analyze`
2. `GET/POST/DELETE /v1/tickets/{id}/tags`
3. `GET /v1/customers`, `GET /v1/customers/{id}`
4. `GET /v1/tenants`, `GET /v1/tenants/{id}`

### Paso 6: Tests

1. Tests de modelos
2. Tests de migraciones
3. Tests de endpoints
4. Tests de permisos
5. Tests de aislamiento por tenant

### Paso 7: Seed

1. Seed de tenants
2. Seed de customers
3. Migración de usuarios existentes

## Criterios de aceptación

- [ ] Tablas creadas con constraints correctos
- [ ] Migraciones preservan datos existentes
- [ ] Endpoint `/analyze` ejecuta en paralelo
- [ ] Tags relacionales funcionan para tickets y artículos
- [ ] Multi-tenant: usuarios pueden estar en múltiples tenants
- [ ] Tests pasan (pytest)
- [ ] No hay regresiones en tests existentes
