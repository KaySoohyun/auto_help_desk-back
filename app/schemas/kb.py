from datetime import datetime

from pydantic import BaseModel, Field


class KbArticleCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10000)
    category: str | None = Field(default=None, max_length=100)
    tags: list[str] = Field(default_factory=list)


class KbArticleUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = Field(default=None, min_length=1, max_length=10000)
    category: str | None = Field(default=None, max_length=100)
    tags: list[str] | None = Field(default=None)
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
    author_name: str | None = None
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
    author_name: str | None = None
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
