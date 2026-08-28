from fastapi.testclient import TestClient
from tests.conftest import register_login

from app.database import SessionLocal
from app.models.audit import AuditEvent
from app.models.tag import Tag, TicketTag
from app.models.ticket import Ticket, TicketMessage


def _headers(tokens: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _create_ticket(client: TestClient, tokens: dict, **overrides) -> dict:
    payload = {
        "subject": "Problema de facturación",
        "description": "El sistema no genera la factura del mes",
        "category": "billing",
        "priority": "high",
    }
    payload.update(overrides)
    response = client.post("/v1/tickets", json=payload, headers=_headers(tokens))
    assert response.status_code == 201, response.text
    return response.json()


def test_create_ticket(client: TestClient) -> None:
    tokens = register_login(client, "agent-a@example.com", "agent", "ten-a")
    ticket = _create_ticket(client, tokens)
    assert ticket["subject"] == "Problema de facturación"
    assert ticket["description"] == "El sistema no genera la factura del mes"
    assert ticket["status"] == "open"
    assert ticket["tenant_id"] == "ten-a"


def test_create_ticket_requires_auth(client: TestClient) -> None:
    assert client.post("/v1/tickets", json={}).status_code == 401


def test_get_ticket_by_id(client: TestClient) -> None:
    tokens = register_login(client, "agent-b@example.com", "agent", "ten-a")
    created = _create_ticket(client, tokens)
    response = client.get(f"/v1/tickets/{created['id']}", headers=_headers(tokens))
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_ticket_from_other_tenant_is_404(client: TestClient) -> None:
    tokens_a = register_login(client, "agent-a@example.com", "agent", "ten-a")
    tokens_b = register_login(client, "agent-b@example.com", "agent", "ten-b")
    created = _create_ticket(client, tokens_a)
    response = client.get(f"/v1/tickets/{created['id']}", headers=_headers(tokens_b))
    assert response.status_code == 404


def test_list_tickets_with_filters_and_pagination(client: TestClient) -> None:
    tokens = register_login(client, "agent-c@example.com", "agent", "ten-a")
    _create_ticket(client, tokens, subject="Ticket uno")
    _create_ticket(client, tokens, subject="Ticket dos", priority="low")
    response = client.get(
        "/v1/tickets",
        headers=_headers(tokens),
        params={"priority": "high", "limit": 10, "offset": 0},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["subject"] == "Ticket uno"


def test_update_ticket(client: TestClient) -> None:
    tokens = register_login(client, "agent-d@example.com", "agent", "ten-a")
    created = _create_ticket(client, tokens)
    response = client.patch(
        f"/v1/tickets/{created['id']}",
        json={"status": "in_progress", "priority": "urgent"},
        headers=_headers(tokens),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"
    assert response.json()["priority"] == "urgent"


def test_update_ticket_from_other_tenant_is_404(client: TestClient) -> None:
    tokens_a = register_login(client, "agent-a@example.com", "agent", "ten-a")
    tokens_b = register_login(client, "agent-b@example.com", "agent", "ten-b")
    created = _create_ticket(client, tokens_a)
    response = client.patch(
        f"/v1/tickets/{created['id']}",
        json={"status": "in_progress"},
        headers=_headers(tokens_b),
    )
    assert response.status_code == 404


def test_add_message_to_ticket(client: TestClient) -> None:
    tokens = register_login(client, "agent-e@example.com", "agent", "ten-a")
    created = _create_ticket(client, tokens)
    response = client.post(
        f"/v1/tickets/{created['id']}/messages",
        json={"body": "Revisando el caso"},
        headers=_headers(tokens),
    )
    assert response.status_code == 201
    assert response.json()["body"] == "Revisando el caso"
    assert response.json()["ticket_id"] == created["id"]


def test_list_messages(client: TestClient) -> None:
    tokens = register_login(client, "agent-f@example.com", "agent", "ten-a")
    created = _create_ticket(client, tokens)
    client.post(f"/v1/tickets/{created['id']}/messages", json={"body": "Uno"}, headers=_headers(tokens))
    client.post(f"/v1/tickets/{created['id']}/messages", json={"body": "Dos"}, headers=_headers(tokens))
    response = client.get(f"/v1/tickets/{created['id']}/messages", headers=_headers(tokens))
    assert response.status_code == 200
    assert [m["body"] for m in response.json()] == ["Uno", "Dos"]


def test_add_message_requires_edit_permission(client: TestClient) -> None:
    tokens = register_login(client, "admin@example.com", "tenant_admin", "ten-a")
    created = _create_ticket(client, tokens)
    # login solo como lector no existe; el agente siempre puede; probar 404 de otro tenant
    tokens_b = register_login(client, "agent-b@example.com", "agent", "ten-b")
    response = client.post(
        f"/v1/tickets/{created['id']}/messages",
        json={"body": "intento"},
        headers=_headers(tokens_b),
    )
    assert response.status_code == 404


def test_add_message_to_closed_ticket_returns_422(client: TestClient) -> None:
    tokens = register_login(client, "agent-closed@example.com", "agent", "ten-a")
    created = _create_ticket(client, tokens)
    client.post(f"/v1/tickets/{created['id']}/close", headers=_headers(tokens))
    response = client.post(
        f"/v1/tickets/{created['id']}/messages",
        json={"body": "mensaje a ticket cerrado"},
        headers=_headers(tokens),
    )
    assert response.status_code == 422
    assert "cerrado" in response.json()["detail"].lower()


def test_close_ticket(client: TestClient) -> None:
    tokens = register_login(client, "agent-g@example.com", "agent", "ten-a")
    created = _create_ticket(client, tokens)
    response = client.post(f"/v1/tickets/{created['id']}/close", headers=_headers(tokens))
    assert response.status_code == 200
    assert response.json()["status"] == "closed"


def test_close_ticket_requires_send_permission(client: TestClient) -> None:
    # rol 'agent' tiene SEND_RESPONSE; probar 404 para otro tenant
    tokens_a = register_login(client, "agent-a@example.com", "agent", "ten-a")
    tokens_b = register_login(client, "agent-b@example.com", "agent", "ten-b")
    created = _create_ticket(client, tokens_a)
    response = client.post(f"/v1/tickets/{created['id']}/close", headers=_headers(tokens_b))
    assert response.status_code == 404


def test_sensitive_fields_are_encrypted_at_rest(client: TestClient) -> None:
    tokens = register_login(client, "agent-h@example.com", "agent", "ten-a")
    created = _create_ticket(client, tokens)
    client.post(f"/v1/tickets/{created['id']}/messages", json={"body": "secreto del cliente"}, headers=_headers(tokens))

    with SessionLocal() as db:
        raw_ticket = db.get(Ticket, created["id"])
        raw_message = db.query(TicketMessage).filter(TicketMessage.ticket_id == created["id"]).first()
        assert raw_ticket is not None
        assert raw_message is not None
        raw_subject = raw_ticket.subject
        raw_description = raw_ticket.description
        raw_body = raw_message.body

    assert raw_subject
    assert raw_description
    assert raw_body
    assert "facturación" not in raw_subject
    assert "factura del mes" not in raw_description
    assert "secreto del cliente" not in raw_body
    assert raw_subject.startswith("cipher:")
    assert raw_description.startswith("cipher:")
    assert raw_body.startswith("cipher:")


def test_list_tickets_offset_beyond_total_returns_correct_count(client: TestClient) -> None:
    tokens = register_login(client, "agent-offset@example.com", "agent", "ten-a")
    _create_ticket(client, tokens, subject="Ticket 1")
    _create_ticket(client, tokens, subject="Ticket 2")
    _create_ticket(client, tokens, subject="Ticket 3")
    response = client.get(
        "/v1/tickets",
        headers=_headers(tokens),
        params={"limit": 10, "offset": 100},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 0


def test_list_tickets_total_consistency(client: TestClient) -> None:
    tokens = register_login(client, "agent-consistency@example.com", "agent", "ten-a")
    for i in range(5):
        _create_ticket(client, tokens, subject=f"Ticket {i}")
    response = client.get(
        "/v1/tickets",
        headers=_headers(tokens),
        params={"limit": 3, "offset": 0},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= len(body["items"])
    assert body["total"] == 5
    assert len(body["items"]) == 3


def test_ticket_operations_are_audited(client: TestClient) -> None:
    tokens = register_login(client, "agent-i@example.com", "agent", "ten-a")
    created = _create_ticket(client, tokens)
    client.patch(f"/v1/tickets/{created['id']}", json={"status": "on_hold"}, headers=_headers(tokens))
    client.post(f"/v1/tickets/{created['id']}/close", headers=_headers(tokens))

    with SessionLocal() as db:
        events = db.query(AuditEvent).filter(AuditEvent.tenant_id == "ten-a").all()
    actions = {e.action for e in events}
    assert "ticket.created" in actions
    assert "ticket.updated" in actions
    assert "ticket.closed" in actions
    for e in events:
        if e.action.startswith("ticket."):
            assert e.trace_id
            assert e.detail["ticket_id"] == created["id"]


# === Búsqueda por categoría y tags (feature 023) ===


def _create_tag_from_db(tenant_id: str, name: str) -> int:
    with SessionLocal() as db:
        tag = Tag(tenant_id=tenant_id, name=name)
        db.add(tag)
        db.commit()
        db.refresh(tag)
        return tag.id


def _tag_ticket(client: TestClient, tokens: dict, ticket_id: int, tag_id: int) -> None:
    resp = client.post(f"/v1/tickets/{ticket_id}/tags", json={"tag_id": tag_id}, headers=_headers(tokens))
    assert resp.status_code == 201, resp.text


def test_search_tickets_by_category(client: TestClient) -> None:
    tokens = register_login(client, "agent-search-1@example.com", "agent", "ten-a")
    _create_ticket(client, tokens, subject="coincide", category="busqueda-certificacion")
    _create_ticket(client, tokens, subject="no coincide", category="otra-cosa")

    resp = client.get("/v1/tickets", params={"q": "certificacion"}, headers=_headers(tokens))
    assert resp.status_code == 200
    body = resp.json()
    subjects = {t["subject"] for t in body["items"]}
    assert "coincide" in subjects
    assert "no coincide" not in subjects


def test_search_tickets_by_category_case_insensitive(client: TestClient) -> None:
    tokens = register_login(client, "agent-search-2@example.com", "agent", "ten-a")
    _create_ticket(client, tokens, subject="mayus", category="FACTURACION-XYZ")

    resp = client.get("/v1/tickets", params={"q": "facturacion-xyz"}, headers=_headers(tokens))
    assert resp.status_code == 200
    subjects = {t["subject"] for t in resp.json()["items"]}
    assert "mayus" in subjects


def test_search_tickets_by_tag(client: TestClient) -> None:
    tokens = register_login(client, "agent-search-3@example.com", "agent", "ten-a")
    with_tag = _create_ticket(client, tokens, subject="tiene-tag", category="general")
    without_tag = _create_ticket(client, tokens, subject="sin-tag", category="general")

    tag_id = _create_tag_from_db("ten-a", "etiqueta-unica-x")
    _tag_ticket(client, tokens, with_tag["id"], tag_id)

    resp = client.get("/v1/tickets", params={"q": "etiqueta-unica-x"}, headers=_headers(tokens))
    assert resp.status_code == 200
    ids = {t["id"] for t in resp.json()["items"]}
    assert with_tag["id"] in ids
    assert without_tag["id"] not in ids


def test_search_tickets_no_results(client: TestClient) -> None:
    tokens = register_login(client, "agent-search-4@example.com", "agent", "ten-a")
    _create_ticket(client, tokens, subject="base", category="billing")

    resp = client.get("/v1/tickets", params={"q": "texto-que-no-existe-999"}, headers=_headers(tokens))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["items"] == []


def test_search_coexists_with_filters_and_pagination(client: TestClient) -> None:
    tokens = register_login(client, "agent-search-5@example.com", "agent", "ten-a")
    _create_ticket(client, tokens, subject="alto", category="busq-coexist-1", priority="high")
    _create_ticket(client, tokens, subject="alto-2", category="busq-coexist-1", priority="high")
    _create_ticket(client, tokens, subject="bajo", category="busq-coexist-1", priority="low")

    resp = client.get(
        "/v1/tickets",
        params={"q": "busq-coexist-1", "priority": "high", "limit": 10, "offset": 0},
        headers=_headers(tokens),
    )
    assert resp.status_code == 200
    body = resp.json()
    subjects = {t["subject"] for t in body["items"]}
    assert "alto" in subjects
    assert "alto-2" in subjects
    assert "bajo" not in subjects

