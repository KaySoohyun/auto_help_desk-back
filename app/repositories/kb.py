from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.models.kb import KbArticle, KbArticleTag, KbArticleVersion
from app.models.tag import Tag
from app.models.user import User
from app.repositories.base import TenantScopedRepository


class KbRepository(TenantScopedRepository[KbArticle]):
    """Repositorio de artículos KB con alcance de uno o varios tenants."""

    def __init__(
        self,
        db: Session,
        tenant_id: str | None = None,
        tenant_ids: list[str] | None = None,
    ) -> None:
        self.tenant_ids = list(dict.fromkeys(tenant_ids or ([tenant_id] if tenant_id else [])))
        self.tenant_id = self.tenant_ids[0] if self.tenant_ids else ""
        super().__init__(db, KbArticle, self.tenant_id)

    def _assert_tenant(self, obj: KbArticle) -> None:
        if getattr(obj, self.tenant_id_attr) not in self.tenant_ids:
            raise PermissionError("Recurso de otro tenant")

    def _get_or_create_tag(self, tag_name: str, tenant_id: str) -> Tag:
        """Obtiene o crea un tag por nombre para el tenant del artículo."""
        tag = self.db.query(Tag).filter(
            Tag.tenant_id == tenant_id,
            Tag.name == tag_name
        ).first()
        if not tag:
            tag = Tag(tenant_id=tenant_id, name=tag_name)
            self.db.add(tag)
            self.db.flush()
        return tag

    def get_tags(self, article_id: int) -> list[str]:
        stmt = (
            select(Tag.name)
            .join(KbArticleTag, KbArticleTag.tag_id == Tag.id)
            .where(KbArticleTag.article_id == article_id)
        )
        return list(self.db.scalars(stmt).all())

    def set_tags(self, article_id: int, tags: list[str]) -> None:
        self.db.execute(delete(KbArticleTag).where(KbArticleTag.article_id == article_id))
        article = self.db.get(KbArticle, article_id)
        tenant_id = article.tenant_id if article is not None else self.tenant_id
        for tag_name in tags:
            tag = self._get_or_create_tag(tag_name, tenant_id)
            self.db.add(KbArticleTag(article_id=article_id, tag_id=tag.id))
        self.db.flush()

    def _with_tags(self, article: KbArticle) -> dict:
        tags = self.get_tags(article.id)
        return {
            "id": article.id,
            "tenant_id": article.tenant_id,
            "title": article.title,
            "body": article.body,
            "category": article.category,
            "tags": tags,
            "status": article.status,
            "author_id": article.author_id,
            "current_version": article.current_version,
            "created_at": article.created_at,
            "updated_at": article.updated_at,
            "published_at": article.published_at,
        }

    def _with_author_names(self, items: list[dict]) -> list[dict]:
        """Rellena `author_name` en los dicts con una query batch por author_id."""
        author_ids = {d.get("author_id") for d in items if d.get("author_id")}
        names: dict[int, str | None] = {}
        if author_ids:
            users = self.db.query(User).filter(User.id.in_(author_ids)).all()
            names = {u.id: u.name for u in users}
        for d in items:
            d["author_name"] = names.get(d.get("author_id"))
        return items

    def _summary(self, article: KbArticle) -> dict:
        data = self._with_tags(article)
        del data["body"]
        return data

    def list(
        self,
        *,
        status: str | None = None,
        category: str | None = None,
        tag: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        filters = [KbArticle.tenant_id.in_(self.tenant_ids)]
        if status:
            filters.append(KbArticle.status == status)
        if category:
            filters.append(KbArticle.category == category)
        if tag:
            # Buscar artículos que tengan el tag por nombre
            tag_subq = (
                select(KbArticleTag.article_id)
                .join(Tag, KbArticleTag.tag_id == Tag.id)
                .where(Tag.name == tag, Tag.tenant_id.in_(self.tenant_ids))
            )
            filters.append(KbArticle.id.in_(tag_subq))
        if search:
            pattern = f"%{search.lower()}%"
            filters.append(
                or_(
                    func.lower(KbArticle.title).like(pattern),
                    func.lower(KbArticle.body).like(pattern),
                )
            )

        count_stmt = select(func.count()).select_from(KbArticle).where(*filters)
        total = self.db.scalar(count_stmt) or 0

        stmt = (
            select(KbArticle)
            .where(*filters)
            .order_by(KbArticle.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        articles = list(self.db.scalars(stmt).all())
        return self._with_author_names([self._summary(a) for a in articles]), total

    def get_or_none(self, pk) -> dict | None:
        article = super().get_or_none(pk)
        if article is None:
            return None
        return self._with_author_names([self._with_tags(article)])[0]

    def create(
        self,
        *,
        title: str,
        body: str,
        category: str | None,
        tags: list[str],
        author_id: int,
    ) -> dict:
        article = KbArticle(
            tenant_id=self.tenant_id,
            title=title,
            body=body,
            category=category,
            status="draft",
            author_id=author_id,
            current_version=1,
        )
        self.db.add(article)
        self.db.flush()
        self.set_tags(article.id, tags)
        version = KbArticleVersion(
            article_id=article.id,
            version=1,
            title=title,
            body=body,
            category=category,
            author_id=author_id,
        )
        self.db.add(version)
        self.db.commit()
        self.db.refresh(article)
        return self._with_author_names([self._with_tags(article)])[0]

    def update(
        self,
        pk,
        *,
        title: str | None = None,
        body: str | None = None,
        category: str | None = None,
        tags: list[str] | None = None,
        change_note: str | None = None,
        author_id: int,
    ) -> dict | None:
        article = super().get_or_none(pk)
        if article is None:
            return None
        if title is not None:
            article.title = title
        if body is not None:
            article.body = body
        if category is not None:
            article.category = category
        article.current_version += 1
        article.updated_at = datetime.now(UTC)
        if tags is not None:
            self.set_tags(article.id, tags)
        version = KbArticleVersion(
            article_id=article.id,
            version=article.current_version,
            title=article.title,
            body=article.body,
            category=article.category,
            author_id=author_id,
            change_note=change_note,
        )
        self.db.add(version)
        self.db.commit()
        self.db.refresh(article)
        return self._with_author_names([self._with_tags(article)])[0]

    def publish(self, pk) -> dict | None:
        article = super().get_or_none(pk)
        if article is None:
            return None
        if article.status != "draft":
            raise ValueError("Solo se puede publicar desde borrador")
        article.status = "published"
        article.published_at = datetime.now(UTC)
        article.updated_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(article)
        return self._with_author_names([self._with_tags(article)])[0]

    def archive(self, pk) -> dict | None:
        article = super().get_or_none(pk)
        if article is None:
            return None
        if article.status != "published":
            raise ValueError("Solo se puede archivar desde publicado")
        article.status = "archived"
        article.updated_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(article)
        return self._with_author_names([self._with_tags(article)])[0]

    def restore(self, pk) -> dict | None:
        article = super().get_or_none(pk)
        if article is None:
            return None
        if article.status != "archived":
            raise ValueError("Solo se puede restaurar desde archivado")
        article.status = "draft"
        article.published_at = None
        article.updated_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(article)
        return self._with_author_names([self._with_tags(article)])[0]

    def list_versions(self, article_id: int) -> list[dict]:
        article = super().get_or_none(article_id)
        if article is None:
            raise PermissionError("Artículo no encontrado")
        stmt = (
            select(KbArticleVersion)
            .where(KbArticleVersion.article_id == article_id)
            .order_by(KbArticleVersion.version.desc())
        )
        versions = list(self.db.scalars(stmt).all())
        result = []
        for v in versions:
            result.append({
                "id": v.id,
                "article_id": v.article_id,
                "version": v.version,
                "title": v.title,
                "body": v.body,
                "category": v.category,
                "tags": self.get_tags(article_id) if v.version == article.current_version else [],
                "author_id": v.author_id,
                "change_note": v.change_note,
                "created_at": v.created_at,
            })
        return self._with_author_names(result)
