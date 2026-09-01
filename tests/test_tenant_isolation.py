import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from tests.conftest import register_login

from app.core.security import hash_password
from app.database import SessionLocal
from app.models.user import User
from app.repositories.base import TenantScopedRepository


def test_users_from_other_tenant_not_visible(client: TestClient) -> None:
    register_login(client, "a1@example.com", "agent", "ten-a")
    register_login(client, "a2@example.com", "agent", "ten-a")
    register_login(client, "b1@example.com", "agent", "ten-b")

    admin_a = register_login(client, "admin@ten-a.com", "tenant_admin", "ten-a")
    response = client.get(
        "/admin/users",
        headers={"Authorization": f"Bearer {admin_a['access_token']}"},
    )
    assert response.status_code == 200
    emails = {u["email"] for u in response.json()["items"]}
    assert "a1@example.com" in emails
    assert "a2@example.com" in emails
    assert "b1@example.com" not in emails
    assert "admin@ten-a.com" in emails


def test_tenant_scoped_repository_blocks_cross_tenant() -> None:
    with SessionLocal() as db:
        tenant_b_user = User(
            email="only-b@example.com",
            password_hash=hash_password("segura-123"),
            role="agent",
            tenant_id="ten-b",
        )
        db.add(tenant_b_user)
        db.commit()
        db.refresh(tenant_b_user)
        other_id = tenant_b_user.id

    with SessionLocal() as db:
        repo_a = TenantScopedRepository(db, User, "ten-a")
        with pytest.raises(PermissionError):
            repo_a.get_or_none(other_id)

    with SessionLocal() as db:
        repo_b = TenantScopedRepository(db, User, "ten-b")
        fetched = repo_b.get_or_none(other_id)
        assert fetched is not None
        assert fetched.email == "only-b@example.com"


def test_repository_list_filters_by_tenant() -> None:
    with SessionLocal() as db:
        db.add(User(email="in-a@example.com", password_hash="x", role="agent", tenant_id="ten-a"))
        db.add(User(email="in-b@example.com", password_hash="x", role="agent", tenant_id="ten-b"))
        db.commit()

    with SessionLocal() as db:
        repo_a = TenantScopedRepository(db, User, "ten-a")
        emails = {u.email for u in repo_a.list()}
        assert "in-a@example.com" in emails
        assert "in-b@example.com" not in emails


def test_repository_add_sets_tenant_from_context() -> None:
    with SessionLocal() as db:
        repo = TenantScopedRepository(db, User, "ten-a")
        created = repo.add(User(email="nuevo@example.com", password_hash=hash_password("x"), role="agent"))
        assert created.tenant_id == "ten-a"

    with SessionLocal() as db:
        stored = db.scalar(select(User).where(User.email == "nuevo@example.com"))
        assert stored is not None
        assert stored.tenant_id == "ten-a"