# 019 · Base de conocimiento — Tareas

**Feature:** [019-base-conocimiento](./)
**Spec:** [spec.md](./spec.md)
**Plan:** [plan.md](./plan.md)

## Tareas

- [x] **T1. Agregar permisos KB** (`app/core/permissions.py`)
  - Agregar `KB_READ = "kb:read"`, `KB_EDIT = "kb:edit"`, `KB_PUBLISH = "kb:publish"`.
  - Actualizar `ROLE_PERMISSIONS`: agent solo `KB_READ`; supervisor/tenant_admin/platform_admin los tres.
  - Verificar alineación con `src/lib/permissions.ts` del frontend.

- [x] **T2. Crear modelos KB** (`app/models/kb.py`)
  - `KbArticle`: id, tenant_id, title, body, category, status, author_id, current_version, created_at, updated_at, published_at.
  - `KbArticleVersion`: id, article_id, version, title, body, category, author_id, change_note, created_at.
  - `KbArticleTag`: id, article_id, tag.
  - Índices: tenant+status, tenant+category, tenant+created_at, article+version, article+tag.
  - Registrar en `app/models/__init__.py`.

- [x] **T3. Crear schemas KB** (`app/schemas/kb.py`)
  - `KbArticleCreate`, `KbArticleUpdate` (inputs).
  - `KbArticleOut`, `KbArticleSummaryOut`, `KbArticleListOut`, `KbArticleVersionOut` (outputs).
  - Configurar alias camelCase (`model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)`).

- [x] **T4. Crear repositorio KB** (`app/repositories/kb.py`)
  - `KbRepository(TenantScopedRepository[KbArticle])`.
  - `list(status, category, tag, search, limit, offset)`: filtro por tenant, búsqueda LIKE, filtro por tag.
  - `get_or_none(pk)`: con tags.
  - `create(title, body, category, tags, author_id)`: versión 1, status draft.
  - `update(pk, title, body, category, tags, change_note, author_id)`: incrementa versión, genera snapshot, actualiza tags.
  - `publish(pk)`: draft → published, setea published_at.
  - `archive(pk)`: published → archived.
  - `restore(pk)`: archived → draft, limpia published_at.
  - `list_versions(article_id)`: historial ordenado por versión desc.
  - `get_tags(article_id)`, `set_tags(article_id, tags)`.
  - Transiciones inválidas → `ValueError`.

- [x] **T5. Crear rutas KB** (`app/api/routes_kb.py`)
  - `GET /v1/kb/articles` (KB_READ).
  - `POST /v1/kb/articles` (KB_EDIT, 201).
  - `GET /v1/kb/articles/{id}` (KB_READ).
  - `PATCH /v1/kb/articles/{id}` (KB_EDIT).
  - `POST /v1/kb/articles/{id}/publish` (KB_PUBLISH).
  - `POST /v1/kb/articles/{id}/archive` (KB_EDIT).
  - `POST /v1/kb/articles/{id}/restore` (KB_EDIT).
  - `GET /v1/kb/articles/{id}/versions` (KB_READ).
  - Isolación: 404 si artículo no existe o es de otro tenant.
  - Auditoría: `kb.article_created`, `kb.article_updated`, `kb.article_published`, `kb.article_archived`, `kb.article_restored`.
  - Registrar router en `app/main.py`.

- [x] **T6. Tests backend** (`tests/test_kb.py`)
  - CRUD básico: crear, listar, detalle, actualizar.
  - Permisos: agent solo lee; supervisor/tenant_admin pueden editar y publicar.
  - Isolación: 404 al acceder a artículos de otro tenant.
  - Versionado: cada PATCH incrementa versión y guarda snapshot.
  - Transiciones: publish desde draft → 200; publish desde published → 422; archive desde published → 200; restore desde archived → 200.
  - Búsqueda: `search` case-insensitive sobre title y body.
  - Filtro por tag: devuelve artículos con ese tag.
  - Auditoría: eventos `kb.*` sin PII.

- [x] **T7. Tests frontend** (`tests/knowledge.test.ts`)
  - Actualizar tests que hoy esperan 404 para validar flujo completo con backend real.
  - Listar artículos, crear, editar, publicar, archivar, restaurar, historial de versiones.
  - Permisos: agent solo lee publicados; supervisor puede gestionar.

- [x] **T8. Documentación**
  - Actualizar `ia_docs/cambios.md` con entrada de la feature.
  - Actualizar `ia-docs/init/plan-fix-backend.md` marcando Hallazgo 2 como completado.
  - Actualizar `ia_docs/constitution/roadmap.md` moviendo feature a "Hecho".

## Criterios de aceptación

- [x] Todos los endpoints responden según el contrato (200, 201, 404, 422).
- [x] Permisos RBAC validados: `kb:read`, `kb:edit`, `kb:publish`.
- [x] Isolación por tenant: 404 al acceder a artículos de otro tenant.
- [x] Versionado: cada PATCH incrementa `current_version` y guarda snapshot.
- [x] Transiciones de estado validadas: 422 si la transición es inválida.
- [x] Búsqueda `search` funciona sobre `title` y `body`.
- [x] Filtro por `tag` funciona sobre tabla normalizada.
- [x] Auditoría de acciones sin PII.
- [x] Tests backend pasan: `pytest` (259 tests).
- [x] Tests frontend pasan: `pnpm test:functional` (106 tests).
- [x] Lint: `pnpm lint` (0 warnings).
- [x] Typecheck: `pnpm typecheck` (0 errores).

## Notas

- Los artículos NO requieren cifrado (no contienen PII).
- Tags normalizados en tabla `kb_article_tags` para portabilidad SQLite/Postgres.
- Las transiciones de estado (publish/archive/restore) NO generan versión.
- El `change_note` es opcional en PATCH y se guarda en el snapshot de versión.
