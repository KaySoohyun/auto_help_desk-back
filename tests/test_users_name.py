"""Feature 018: el campo `name` de los usuarios (registro, admin, exposición)."""

from fastapi.testclient import TestClient

from tests.conftest import register_login

from app.core.security import hash_password
from app.database import SessionLocal
from app.models.user import User


def _headers(tokens: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _me(client: TestClient, tokens: dict) -> dict:
    response = client.get("/auth/me", headers=_headers(tokens))
    assert response.status_code == 200, response.text
    return response.json()


def test_register_requires_name(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={"email": "noname@example.com", "password": "segura-123", "role": "agent"},
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any("Campo requerido" in str(e["msg"]) and "name" in str(e["loc"]) for e in detail)


def test_register_stores_name(client: TestClient) -> None:
    tokens = register_login(client, "named@example.com", "agent", "ten-a")
    me = _me(client, tokens)
    assert me["name"] == "Test Usuario"


def test_admin_creates_user_with_name(client: TestClient) -> None:
    admin = register_login(client, "admin-n@example.com", "platform_admin")
    response = client.post(
        "/admin/users",
        json={
            "email": "nuevo@example.com",
            "name": "Nuevo Agente",
            "password": "segura-123",
            "role": "agent",
            "tenant_id": "ten-a",
        },
        headers=_headers(admin),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "Nuevo Agente"


def test_admin_create_user_requires_name(client: TestClient) -> None:
    admin = register_login(client, "admin-n2@example.com", "platform_admin")
    response = client.post(
        "/admin/users",
        json={"email": "nuevo2@example.com", "password": "segura-123", "role": "agent", "tenant_id": "ten-a"},
        headers=_headers(admin),
    )
    assert response.status_code == 422


def test_admin_updates_user_name(client: TestClient) -> None:
    admin = register_login(client, "admin-n3@example.com", "platform_admin")
    created = client.post(
        "/admin/users",
        json={
            "email": "editable@example.com",
            "name": "Antes",
            "password": "segura-123",
            "role": "agent",
            "tenant_id": "ten-a",
        },
        headers=_headers(admin),
    ).json()
    response = client.patch(
        f"/admin/users/{created['id']}",
        json={"name": "Despues"},
        headers=_headers(admin),
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Despues"


def test_admin_list_users_includes_name(client: TestClient) -> None:
    admin = register_login(client, "list-admin@example.com", "tenant_admin", "ten-a")
    created = client.post(
        "/admin/users",
        json={"email": "listado@example.com", "name": "Listado", "password": "segura-123", "role": "agent", "tenant_id": "ten-a"},
        headers=_headers(admin),
    )
    assert created.status_code == 201, created.text
    response = client.get("/admin/users", headers=_headers(admin))
    assert response.status_code == 200
    body = response.json()
    assert any(u["email"] == "listado@example.com" and u["name"] == "Listado" for u in body["items"])


def test_me_exposes_null_name_for_legacy_users(client: TestClient) -> None:
    # Usuarios insertados directo (sin name) devuelven None, no rompe nada.
    with SessionLocal() as db:
        db.add(
            User(
                email="legacy@example.com",
                password_hash=hash_password("segura-123"),
                role="agent",
                tenant_id="ten-a",
                is_active=True,
                name=None,
            )
        )
        db.commit()
    login = client.post("/auth/login", json={"email": "legacy@example.com", "password": "segura-123"})
    assert login.status_code == 200
    me = _me(client, login.json())
    assert me["name"] is None