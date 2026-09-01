"""Tests del portal de personas (rol customer): mis tickets, aislamiento y mensajes."""

from fastapi.testclient import TestClient
from tests.conftest import register_login

from app.database import SessionLocal
from app.models.customer import Customer


def _headers(tokens: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _register_customer(client: TestClient, email: str, tenant_id: str = "ten-1") -> dict:
    return register_login(client, email, "customer", tenant_id)


def _create_ticket(client: TestClient, tokens: dict, subject: str = "mi ticket") -> dict:
    resp = client.post(
        "/v1/me/tickets",
        json={"subject": subject, "description": "descripcion", "category": "billing", "priority": "high"},
        headers=_headers(tokens),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# === Registro customer ===


def test_register_customer_creates_profile(client: TestClient) -> None:
    tokens = _register_customer(client, "c1@example.com")
    resp = client.get("/auth/me", headers=_headers(tokens))
    assert resp.status_code == 200
    me = resp.json()
    assert me["role"] == "customer"
    assert me["tenant_id"] == "ten-1"

    with SessionLocal() as db:
        customer = db.query(Customer).filter(Customer.user_id == me["id"]).first()
        assert customer is not None
        assert customer.email == "c1@example.com"
        assert customer.tenant_id == "ten-1"


def test_customer_list_and_create_flow(client: TestClient) -> None:
    tokens = _register_customer(client, "c2@example.com")

    empty = client.get("/v1/me/tickets", headers=_headers(tokens))
    assert empty.status_code == 200
    assert empty.json()["total"] == 0

    ticket = _create_ticket(client, tokens, "problema de facturación")
    assert ticket["customer_id"] is not None
    assert ticket["status"] == "open"

    listing = client.get("/v1/me/tickets", headers=_headers(tokens))
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["subject"] == "problema de facturación"

    detail = client.get(f"/v1/me/tickets/{ticket['id']}", headers=_headers(tokens))
    assert detail.status_code == 200
    assert detail.json()["id"] == ticket["id"]


# === Aislamiento ===


def test_customer_isolation_cross_customer(client: TestClient) -> None:
    tokens_a = _register_customer(client, "cA@example.com")
    tokens_b = _register_customer(client, "cB@example.com")
    ticket = _create_ticket(client, tokens_a, "ticket de A")

    # B no ve el ticket de A
    listing = client.get("/v1/me/tickets", headers=_headers(tokens_b))
    assert listing.json()["total"] == 0
    assert client.get(f"/v1/me/tickets/{ticket['id']}", headers=_headers(tokens_b)).status_code == 404
    assert client.get(f"/v1/me/tickets/{ticket['id']}/messages", headers=_headers(tokens_b)).status_code == 404


def test_customer_isolation_cross_tenant(client: TestClient) -> None:
    tokens_a = _register_customer(client, "cT1@example.com", tenant_id="ten-1")
    tokens_b = _register_customer(client, "cT2@example.com", tenant_id="ten-2")
    ticket = _create_ticket(client, tokens_a, "ticket ten-1")

    listing = client.get("/v1/me/tickets", headers=_headers(tokens_b))
    assert listing.json()["total"] == 0
    assert client.get(f"/v1/me/tickets/{ticket['id']}", headers=_headers(tokens_b)).status_code == 404


def test_customer_isolation_cross_tenant_same_user_scope(client: TestClient) -> None:
    """Un customer con varios tenants solo ve sus tickets (los ajenos no aparecen)."""
    tokens_a = _register_customer(client, "cM1@example.com", tenant_id="ten-1")
    _register_customer(client, "cM2@example.com", tenant_id="ten-2")
    _create_ticket(client, tokens_a, "ticket propio")

    # Customer de ten-2 con acceso a ambos tenants (vía membresía) no ve tickets ajenos
    client.post(
        "/auth/register",
        json={"name": "Test Usuario", "email": "cM3@example.com", "password": "segura-123", "role": "customer", "tenant_ids": ["ten-1", "ten-2"]},
    )
    login = client.post("/auth/login", json={"email": "cM3@example.com", "password": "segura-123"})
    tokens_c = login.json()
    assert client.get("/v1/me/tickets", headers=_headers(tokens_c)).json()["total"] == 0


def test_non_customer_forbidden(client: TestClient) -> None:
    tokens = register_login(client, "agent-x@example.com", "agent", "ten-1")
    assert client.get("/v1/me/tickets", headers=_headers(tokens)).status_code == 403
    assert client.post(
        "/v1/me/tickets",
        json={"subject": "no", "description": "no"},
        headers=_headers(tokens),
    ).status_code == 403


# === Mensajes ===


def test_customer_messages_flow(client: TestClient) -> None:
    tokens = _register_customer(client, "cMsg@example.com")
    ticket = _create_ticket(client, tokens, "conversación")

    sent = client.post(
        f"/v1/me/tickets/{ticket['id']}/messages",
        json={"body": "hola, necesito ayuda"},
        headers=_headers(tokens),
    )
    assert sent.status_code == 201
    assert sent.json()["author_id"] is not None

    thread = client.get(f"/v1/me/tickets/{ticket['id']}/messages", headers=_headers(tokens))
    assert thread.status_code == 200
    assert [m["body"] for m in thread.json()] == ["hola, necesito ayuda"]


def test_customer_message_on_closed_ticket_422(client: TestClient) -> None:
    tokens = _register_customer(client, "cClosed@example.com")
    ticket = _create_ticket(client, tokens, "cerrado")
    # El ticket del customer solo lo cierra un agente; se fuerza el cierre en la DB.
    with SessionLocal() as db:
        from app.models.ticket import Ticket as TicketModel

        t = db.get(TicketModel, ticket["id"])
        t.status = "closed"
        db.commit()

    resp = client.post(
        f"/v1/me/tickets/{ticket['id']}/messages",
        json={"body": "mensaje tardío"},
        headers=_headers(tokens),
    )
    assert resp.status_code == 422


# === Búsqueda por categoría/tags (feature 023) ===


def test_customer_search_by_category(client: TestClient) -> None:
    tokens = _register_customer(client, "cBusq@example.com")

    def post(subject: str, category: str) -> None:
        resp = client.post(
            "/v1/me/tickets",
            json={"subject": subject, "description": "desc", "category": category, "priority": "high"},
            headers=_headers(tokens),
        )
        assert resp.status_code == 201, resp.text

    post("ticket a", "busq-cliente-soporte")
    post("ticket b", "busq-cliente-otro")

    resp = client.get("/v1/me/tickets", params={"q": "soporte"}, headers=_headers(tokens))
    assert resp.status_code == 200
    subjects = {t["subject"] for t in resp.json()["items"]}
    assert "ticket a" in subjects
    assert "ticket b" not in subjects


def test_customer_search_no_results(client: TestClient) -> None:
    tokens = _register_customer(client, "cBusq2@example.com")
    _create_ticket(client, tokens, "ticket base")
    resp = client.get("/v1/me/tickets", params={"q": "no-existe-abc"}, headers=_headers(tokens))
    body = resp.json()
    assert body["total"] == 0
    assert body["items"] == []

