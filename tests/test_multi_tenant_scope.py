"""Tests del alcance multi-tenant (registro con varios tenants) y tenants públicos."""

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.models.tenant import Tenant


def _headers(tokens: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _create_ticket(client: TestClient, tokens: dict, subject: str = "ticket") -> int:
    resp = client.post(
        "/v1/tickets",
        json={"subject": subject, "description": "desc", "priority": "medium"},
        headers=_headers(tokens),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _register(client: TestClient, email: str, tenant_ids: list[str]) -> None:
    resp = client.post(
        "/auth/register",
        json={
            "name": "Test Usuario",
            "email": email,
            "password": "segura-123",
            "role": "agent",
            "tenant_ids": tenant_ids,
        },
    )
    assert resp.status_code == 201, resp.text


# === Registro con varios tenants ===


def test_register_with_multiple_tenants_creates_memberships(client: TestClient) -> None:
    resp = client.post(
        "/auth/register",
        json={
            "name": "Test Usuario",
            "email": "multi@example.com",
            "password": "segura-123",
            "role": "agent",
            "tenant_ids": ["ten-a", "ten-b"],
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["tenant_id"] is None  # sin tenant principal → ve todos al saltar
    assert {t["id"] for t in data["tenants"]} == {"ten-a", "ten-b"}

    login = client.post("/auth/login", json={"email": "multi@example.com", "password": "segura-123"})
    assert login.status_code == 200
    me = client.get("/auth/me", headers=_headers(login.json()))
    assert {t["id"] for t in me.json()["tenants"]} == {"ten-a", "ten-b"}


def test_register_single_tenant_sets_primary(client: TestClient) -> None:
    resp = client.post(
        "/auth/register",
        json={
            "name": "Test Usuario",
            "email": "single@example.com",
            "password": "segura-123",
            "role": "agent",
            "tenant_ids": ["ten-a"],
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["tenant_id"] == "ten-a"
    assert len(data["tenants"]) == 1


def test_register_rejects_unknown_tenant(client: TestClient) -> None:
    resp = client.post(
        "/auth/register",
        json={
            "name": "Test Usuario",
            "email": "ghost@example.com",
            "password": "segura-123",
            "role": "agent",
            "tenant_ids": ["no-existe"],
        },
    )
    assert resp.status_code == 404


# === Alcance de tickets multi-tenant ===


def test_tickets_scope_all_tenants_when_skipped(client: TestClient) -> None:
    """Sin seleccionar tenant, el usuario ve tickets de todos sus tenants."""
    agent_a = _register_and_login(client, "a@example.com", tenant_id="ten-a")
    agent_b = _register_and_login(client, "b@example.com", tenant_id="ten-b")
    _create_ticket(client, agent_a, "ticket-a")
    _create_ticket(client, agent_b, "ticket-b")

    _register(client, "multi@example.com", ["ten-a", "ten-b"])
    login = client.post("/auth/login", json={"email": "multi@example.com", "password": "segura-123"})
    tokens = login.json()

    resp = client.get("/v1/tickets", headers=_headers(tokens))
    assert resp.status_code == 200
    subjects = {t["subject"] for t in resp.json()["items"]}
    assert {"ticket-a", "ticket-b"} <= subjects


def test_tickets_scope_single_selected_tenant(client: TestClient) -> None:
    """Con tenant seleccionado, el usuario solo ve tickets de ese tenant."""
    agent_a = _register_and_login(client, "a@example.com", tenant_id="ten-a")
    agent_b = _register_and_login(client, "b@example.com", tenant_id="ten-b")
    _create_ticket(client, agent_a, "solo-a")
    _create_ticket(client, agent_b, "solo-b")

    _register(client, "multi@example.com", ["ten-a", "ten-b"])
    login = client.post(
        "/auth/login",
        json={"email": "multi@example.com", "password": "segura-123", "tenant_id": "ten-a"},
    )
    tokens = login.json()

    resp = client.get("/v1/tickets", headers=_headers(tokens))
    assert resp.status_code == 200
    subjects = {t["subject"] for t in resp.json()["items"]}
    assert "solo-a" in subjects
    assert "solo-b" not in subjects


def _register_and_login(client: TestClient, email: str, tenant_id: str) -> dict:
    client.post(
        "/auth/register",
        json={
            "name": "Test Usuario",
            "email": email,
            "password": "segura-123",
            "role": "agent",
            "tenant_ids": [tenant_id],
        },
    )
    login = client.post("/auth/login", json={"email": email, "password": "segura-123"})
    assert login.status_code == 200, login.text
    return login.json()


# === Tenants públicos ===


def test_public_tenants_endpoint(client: TestClient) -> None:
    resp = client.get("/v1/tenants/public")
    assert resp.status_code == 200
    ids = {t["id"] for t in resp.json()}
    assert {"ten-a", "ten-b"} <= ids
    # Sin auth y sin datos sensibles
    assert all(set(t.keys()) == {"id", "name", "slug", "created_at"} for t in resp.json())


def test_seed_tenants_exist(client: TestClient) -> None:
    """Los tenants sembrados en conftest existen (requisito del registro)."""
    with SessionLocal() as db:
        assert db.get(Tenant, "ten-a") is not None
        assert db.get(Tenant, "ten-b") is not None
