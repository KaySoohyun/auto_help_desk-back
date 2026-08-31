# 019 · Base de conocimiento (KB)

**Estado:** propuesta.
**Alcance:** Implementación de endpoints KB en el backend FastAPI para soportar el Feature 007 del frontend.
**Dependencia:** Feature 007 del frontend ya implementada (BFF + UI).

## Qué hace

Implementa los endpoints `/v1/kb/*` en FastAPI para gestionar artículos de base de conocimiento por tenant: listado, creación, detalle, actualización, publicación, archivado, restauración e historial de versiones.

## Por qué

El frontend (Feature 007) ya tiene la UI completa y el BFF proxya a `/v1/kb/*`, pero el backend no tiene estos endpoints → todos devuelven 404. Esta feature cierra el gap y habilita la funcionalidad end-to-end.

## Contexto

- El frontend define los contratos en `src/types/knowledge.types.ts` y los BFF route handlers en `src/app/api/bff/knowledge/**`.
- El backend sigue patrones existentes: `TenantScopedRepository`, permisos RBAC, auditoría, errores `{"detail": "..."}`.
- Los artículos NO contienen PII sensible (son conocimiento operativo interno), por lo que NO requieren cifrado en reposo (decisión de diseño #1).

## Contratos (alineados al frontend)

### Endpoints

| Método | Ruta | Permiso | Descripción |
| --- | --- | --- | --- |
| GET | `/v1/kb/articles` | `kb:read` | Lista artículos (sin `body`). Query: `status`, `category`, `tag`, `search`, `limit`, `offset` |
| POST | `/v1/kb/articles` | `kb:edit` | Crea artículo en `draft` |
| GET | `/v1/kb/articles/{id}` | `kb:read` | Detalle con `body` |
| PATCH | `/v1/kb/articles/{id}` | `kb:edit` | Actualiza título/cuerpo/categoría/tags; genera snapshot de versión |
| POST | `/v1/kb/articles/{id}/publish` | `kb:publish` | `draft → published` |
| POST | `/v1/kb/articles/{id}/archive` | `kb:edit` | `published → archived` |
| POST | `/v1/kb/articles/{id}/restore` | `kb:edit` | `archived → draft` |
| GET | `/v1/kb/articles/{id}/versions` | `kb:read` | Historial de versiones |

### Schemas

**KbArticleOut** (respuesta completa):
```json
{
  "id": 1,
  "tenant_id": "ten-1",
  "title": "Cómo resetear contraseña",
  "body": "Pasos para resetear...",
  "category": "account",
  "tags": ["password", "login"],
  "status": "published",
  "author_id": 5,
  "current_version": 3,
  "created_at": "2026-08-13T10:00:00Z",
  "updated_at": "2026-08-13T12:00:00Z",
  "published_at": "2026-08-13T11:00:00Z"
}
```

**KbArticleSummaryOut** (ítem de listas, sin `body`): igual que `KbArticleOut` pero sin campo `body`.

**KbArticleListOut**:
```json
{
  "items": [KbArticleSummaryOut],
  "total": 42,
  "limit": 50,
  "offset": 0
}
```

**KbArticleVersionOut**:
```json
{
  "id": 10,
  "article_id": 1,
  "version": 2,
  "title": "Cómo resetear contraseña",
  "body": "Versión anterior...",
  "category": "account",
  "tags": ["password"],
  "author_id": 5,
  "change_note": "Corrección ortográfica",
  "created_at": "2026-08-13T11:00:00Z"
}
```

### Permisos (alineados al frontend `src/lib/permissions.ts`)

- `kb:read`: todos los roles con tenant (agent, supervisor, tenant_admin, platform_admin).
- `kb:edit`: supervisor, tenant_admin (crear, editar, archivar, restaurar).
- `kb:publish`: supervisor, tenant_admin (publicar).

## Decisiones de diseño

1. **Sin cifrado**: los artículos son conocimiento operativo interno, no contienen PII. El cifrado impediría búsqueda `LIKE` (decisión documentada en plan-fix-backend.md Hallazgo 2).
2. **Tags normalizados**: tabla `kb_article_tags` (id, article_id, tag) para portabilidad SQLite/Postgres (sin funciones JSON de dialecto).
3. **Versionado por snapshot**: cada PATCH genera una `KbArticleVersion` con `current_version+1`. Las transiciones de estado (publish/archive/restore) NO generan versión.
4. **Transiciones explícitas**: validar cada transición de estado con 422 si es inválida:
   - `publish`: solo desde `draft`.
   - `archive`: solo desde `published`.
   - `restore`: solo desde `archived`.
5. **Búsqueda `search`**: `LIKE` case-insensitive sobre `title` y `body` (`func.lower()`).
6. **Filtro por `tag`**: búsqueda en tabla `kb_article_tags` por tag exacto.
7. **Isolación por tenant**: todos los endpoints filtran por `tenant_id` del usuario; 404 si el artículo no existe o es de otro tenant.
8. **Auditoría**: eventos `kb.article_created`, `kb.article_updated`, `kb.article_published`, `kb.article_archived`, `kb.article_restored` sin PII.

## Criterios de aceptación

- [ ] Los 8 endpoints responden según el contrato (200, 201, 404, 422 según corresponda).
- [ ] Permisos RBAC validados: `kb:read`, `kb:edit`, `kb:publish` alineados al frontend.
- [ ] Isolación por tenant: 404 al acceder a artículos de otro tenant.
- [ ] Versionado: cada PATCH incrementa `current_version` y guarda snapshot.
- [ ] Transiciones de estado validadas: 422 si la transición es inválida.
- [ ] Búsqueda `search` funciona sobre `title` y `body` (case-insensitive).
- [ ] Filtro por `tag` funciona sobre tabla normalizada.
- [ ] Auditoría de acciones sin PII.
- [ ] Tests unitarios y de integración pasan.
- [ ] Suite frontend (82 tests) pasa con backend real.

## Fuera de alcance

- Cifrado de artículos (no contienen PII).
- Búsqueda semántica / full-text avanzado.
- Workflow de revisión/aprobación.
- Rollback de versiones.
- Métricas de uso.
