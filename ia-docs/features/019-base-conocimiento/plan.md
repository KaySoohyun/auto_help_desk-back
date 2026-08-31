# 019 · Base de conocimiento — Plan de implementación

**Feature:** 019-base-conocimiento
**Spec:** [spec.md](./spec.md)
**Dependencia:** Feature 007 del frontend (BFF + UI ya implementados).

## Piezas a implementar

### 1. Permisos (`app/core/permissions.py`)

Agregar permisos KB al catálogo RBAC:

```python
KB_READ = "kb:read"
KB_EDIT = "kb:edit"
KB_PUBLISH = "kb:publish"

ROLE_PERMISSIONS = {
    "agent": {..., KB_READ},
    "supervisor": {..., KB_READ, KB_EDIT, KB_PUBLISH},
    "tenant_admin": {..., KB_READ, KB_EDIT, KB_PUBLISH},
    "platform_admin": {..., KB_READ, KB_EDIT, KB_PUBLISH},
}
```

Alineado con `src/lib/permissions.ts` del frontend.

### 2. Modelos (`app/models/kb.py`)

**KbArticle**:
```python
class KbArticle(Base):
    __tablename__ = "kb_articles"
    __table_args__ = (
        Index("ix_kb_articles_tenant_status", "tenant_id", "status"),
        Index("ix_kb_articles_tenant_category", "tenant_id", "category"),
        Index("ix_kb_articles_tenant_created", "tenant_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    current_version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

**KbArticleVersion** (snapshot por versión):
```python
class KbArticleVersion(Base):
    __tablename__ = "kb_article_versions"
    __table_args__ = (
        Index("ix_kb_versions_article_version", "article_id", "version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("kb_articles.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column()
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    change_note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
```

**KbArticleTag** (tabla normalizada para tags):
```python
class KbArticleTag(Base):
    __tablename__ = "kb_article_tags"
    __table_args__ = (
        Index("ix_kb_tags_article_tag", "article_id", "tag"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("kb_articles.id", ondelete="CASCADE"), index=True)
    tag: Mapped[str] = mapped_column(String(50), index=True)
```

Registrar modelos en `app/models/__init__.py`.

### 3. Schemas (`app/schemas/kb.py`)

```python
class KbArticleCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10000)
    category: str | None = Field(default=None, max_length=100)
    tags: list[str] = Field(default_factory=list, max_length=10)

class KbArticleUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = Field(default=None, min_length=1, max_length=10000)
    category: str | None = Field(default=None, max_length=100)
    tags: list[str] | None = Field(default=None, max_length=10)
    change_note: str | None = Field(default=None, max_length=200)

class KbArticleOut(BaseModel):
    id: int
    tenant_id: str
    title: str
    body: str
    category: str | None
    tags: list[str]
    status: str
    author_id: int
    current_version: int
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None

class KbArticleSummaryOut(BaseModel):
    id: int
    tenant_id: str
    title: str
    category: str | None
    tags: list[str]
    status: str
    author_id: int
    current_version: int
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None

class KbArticleListOut(BaseModel):
    items: list[KbArticleSummaryOut]
    total: int
    limit: int
    offset: int

class KbArticleVersionOut(BaseModel):
    id: int
    article_id: int
    version: int
    title: str
    body: str
    category: str | None
    tags: list[str]
    author_id: int
    change_note: str | None
    created_at: datetime
```

Campos en camelCase (Pydantic `model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)`).

### 4. Repositorio (`app/repositories/kb.py`)

```python
class KbRepository(TenantScopedRepository[KbArticle]):
    def list(self, *, status, category, tag, search, limit, offset) -> tuple[list[KbArticle], int]
    def get_or_none(self, pk) -> KbArticle | None
    def create(self, *, title, body, category, tags, author_id) -> KbArticle
    def update(self, pk, *, title, body, category, tags, change_note, author_id) -> KbArticle | None
    def publish(self, pk) -> KbArticle | None
    def archive(self, pk) -> KbArticle | None
    def restore(self, pk) -> KbArticle | None
    def list_versions(self, article_id) -> list[KbArticleVersion]
    def get_tags(self, article_id) -> list[str]
    def set_tags(self, article_id, tags: list[str])
```

- `list`: filtro por tenant obligatorio; búsqueda `LIKE` sobre `title` y `body`; filtro por tag en tabla `kb_article_tags`.
- `create`: versión 1, status `draft`, `published_at` null.
- `update`: incrementa `current_version`, genera snapshot en `KbArticleVersion`, actualiza tags.
- `publish`: transición `draft → published`, setea `published_at`.
- `archive`: transición `published → archived`.
- `restore`: transición `archived → draft`, limpia `published_at`.
- Transiciones inválidas → `ValueError` (mapeado a 422 en la ruta).

### 5. Rutas (`app/api/routes_kb.py`)

```python
router = APIRouter(prefix="/v1/kb", tags=["kb"])

@router.get("/articles")
def list_articles(...) -> KbArticleListOut

@router.post("/articles", status_code=201)
def create_article(...) -> KbArticleOut

@router.get("/articles/{article_id}")
def get_article(...) -> KbArticleOut

@router.patch("/articles/{article_id}")
def update_article(...) -> KbArticleOut

@router.post("/articles/{article_id}/publish")
def publish_article(...) -> KbArticleOut

@router.post("/articles/{article_id}/archive")
def archive_article(...) -> KbArticleOut

@router.post("/articles/{article_id}/restore")
def restore_article(...) -> KbArticleOut

@router.get("/articles/{article_id}/versions")
def list_versions(...) -> list[KbArticleVersionOut]
```

- Permisos: `require_permissions(KB_READ)`, `require_permissions(KB_EDIT)`, `require_permissions(KB_PUBLISH)`.
- Isolación: 404 si el artículo no existe o es de otro tenant.
- Auditoría: `kb.article_created`, `kb.article_updated`, `kb.article_published`, `kb.article_archived`, `kb.article_restored`.

Registrar router en `app/main.py`.

### 6. Tests (`tests/test_kb.py`)

- CRUD básico: crear, listar, detalle, actualizar.
- Permisos: agent solo lee; supervisor/tenant_admin pueden editar y publicar.
- Isolación: 404 al acceder a artículos de otro tenant.
- Versionado: cada PATCH incrementa versión y guarda snapshot.
- Transiciones: publish desde draft → 200; publish desde published → 422; archive desde published → 200; restore desde archived → 200.
- Búsqueda: `search` case-insensitive sobre title y body.
- Filtro por tag: devuelve artículos con ese tag.
- Auditoría: eventos `kb.*` sin PII.

### 7. Actualizar tests del frontend

`tests/knowledge.test.ts` hoy espera 404 en todos los endpoints. Actualizar para validar el flujo completo con backend real.

## Orden de implementación

1. Permisos (`app/core/permissions.py`).
2. Modelos (`app/models/kb.py` + registro en `__init__.py`).
3. Schemas (`app/schemas/kb.py`).
4. Repositorio (`app/repositories/kb.py`).
5. Rutas (`app/api/routes_kb.py` + registro en `main.py`).
6. Tests backend (`tests/test_kb.py`).
7. Tests frontend (`tests/knowledge.test.ts`).

## Verificación

- Backend: `pytest` (236 → ~260 tests).
- Frontend: `pnpm test:functional` (95 → ~103 tests, knowledge.test.ts pasa).
- Lint: `pnpm lint` (0 warnings).
- Typecheck: `pnpm typecheck` (0 errores).
