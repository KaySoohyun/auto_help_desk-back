import pytest
from fastapi.testclient import TestClient

from app import __version__
from app.core.config import settings
from app.main import app


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__


def test_register_creates_user(client: TestClient) -> None:
    payload = {
        "email": "admin@example.com",
        "name": "Test Usuario",
        "password": "segura-123",
        "role": "agent",
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "admin@example.com"
    assert "password_hash" not in body


def test_register_rejects_admin_roles(client: TestClient) -> None:
    for role in ("platform_admin", "tenant_admin"):
        response = client.post(
            "/auth/register",
            json={"name": "Test Usuario", "email": f"{role}@example.com", "password": "segura-123", "role": role},
        )
        assert response.status_code == 403
        assert "Rol no permitido" in response.json()["detail"]


def test_register_duplicate_email(client: TestClient) -> None:
    payload = {
        "email": "dup@example.com",
        "name": "Test Usuario",
        "password": "segura-123",
        "role": "agent",
    }
    first = client.post("/auth/register", json=payload)
    second = client.post("/auth/register", json=payload)
    assert first.status_code == 201
    assert second.status_code == 409


def test_login_returns_tokens(client: TestClient) -> None:
    client.post(
        "/auth/register",
        json={"name": "Test Usuario", "email": "agent@example.com", "password": "segura-123", "role": "agent", "tenant_id": "ten-1"},
    )
    response = client.post("/auth/login", json={"email": "agent@example.com", "password": "segura-123"})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["expires_in"] == settings.access_token_expire_minutes * 60


def test_login_wrong_password(client: TestClient) -> None:
    client.post(
        "/auth/register",
        json={"name": "Test Usuario", "email": "bad@example.com", "password": "segura-123", "role": "agent"},
    )
    response = client.post("/auth/login", json={"email": "bad@example.com", "password": "incorrecta"})
    assert response.status_code == 401


def test_me_requires_token(client: TestClient) -> None:
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_me_with_valid_token(client: TestClient) -> None:
    client.post(
        "/auth/register",
        json={"name": "Test Usuario", "email": "me@example.com", "password": "segura-123", "role": "agent", "tenant_id": "ten-1"},
    )
    login = client.post("/auth/login", json={"email": "me@example.com", "password": "segura-123"})
    token = login.json()["access_token"]

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "me@example.com"
    assert body["role"] == "agent"
    assert body["tenant_id"] == "ten-1"


def test_refresh_rotates_token(client: TestClient) -> None:
    client.post(
        "/auth/register",
        json={"name": "Test Usuario", "email": "rot@example.com", "password": "segura-123", "role": "agent", "tenant_id": "ten-1"},
    )
    login = client.post("/auth/login", json={"email": "rot@example.com", "password": "segura-123"})
    old_refresh = login.json()["refresh_token"]

    response = client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"] != old_refresh

    # El refresh viejo ya no debe servir (rotación)
    replay = client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert replay.status_code == 401


def test_logout_revokes_refresh(client: TestClient) -> None:
    client.post(
        "/auth/register",
        json={"name": "Test Usuario", "email": "out@example.com", "password": "segura-123", "role": "agent", "tenant_id": "ten-1"},
    )
    login = client.post("/auth/login", json={"email": "out@example.com", "password": "segura-123"})
    refresh_token = login.json()["refresh_token"]

    logout = client.post("/auth/logout", json={"refresh_token": refresh_token})
    assert logout.status_code == 204

    replay = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert replay.status_code == 401


def test_access_token_invalid(client: TestClient) -> None:
    response = client.get("/auth/me", headers={"Authorization": "Bearer no-valido"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Token inválido"


def test_access_token_claims(client: TestClient) -> None:
    import jwt as pyjwt

    client.post(
        "/auth/register",
        json={"name": "Test Usuario", "email": "claims@example.com", "password": "segura-123", "role": "agent", "tenant_id": "ten-1"},
    )
    login = client.post("/auth/login", json={"email": "claims@example.com", "password": "segura-123"})
    token = login.json()["access_token"]

    payload = pyjwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.jwt_algorithm],
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
    )
    assert payload["sub"]
    assert payload["exp"] > 0
    assert payload["iss"] == settings.jwt_issuer
    assert payload["aud"] == settings.jwt_audience
    assert payload["tenant_id"] == "ten-1"
    assert payload["roles"] == ["agent"]

