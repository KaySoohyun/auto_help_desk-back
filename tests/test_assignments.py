"""Feature 018: reglas de asignación de tickets y endpoint /v1/agents."""

from fastapi.testclient import TestClient

from tests.conftest import register_login

from app.core.security import hash_password
from app.database import SessionLocal
from app.models.user import User


def _headers(tokens: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _user_id(client: TestClient, tokens: dict) -> int:
    response = client.get("/auth/me", headers=_headers(tokens))
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _create_ticket(client: TestClient, tokens: dict) -> dict:
    response = client.post(
        "/v1/tickets",
        json={"subject": "Ticket de asignación", "description": "Contenido del ticket", "category": "general"},
        headers=_headers(tokens),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _set_assignee(client: TestClient, tokens: dict, ticket_id: int, assignee_id: int | None) -> dict:
    return client.patch(
        f"/v1/tickets/{ticket_id}",
        json={"assignee_id": assignee_id},
        headers=_headers(tokens),
    )


# --- agent: solo se asigna a sí mismo -------------------------------------


def test_agent_can_assign_self(client: TestClient) -> None:
    tokens = register_login(client, "self@example.com", "agent", "ten-a")
    me = _user_id(client, tokens)
    ticket = _create_ticket(client, tokens)
    response = _set_assignee(client, tokens, ticket["id"], me)
    assert response.status_code == 200
    assert response.json()["assignee_id"] == me
    assert response.json()["assignee"]["name"] == "Test Usuario"


def test_agent_cannot_assign_other(client: TestClient) -> None:
    tokens = register_login(client, "agent1@example.com", "agent", "ten-a")
    other = _user_id(client, register_login(client, "agent2@example.com", "agent", "ten-a"))
    ticket = _create_ticket(client, tokens)
    response = _set_assignee(client, tokens, ticket["id"], other)
    assert response.status_code == 403
    assert "vos mismo" in response.json()["detail"]


def test_agent_can_unassign(client: TestClient) -> None:
    tokens = register_login(client, "agent-unassign@example.com", "agent", "ten-a")
    me = _user_id(client, tokens)
    ticket = _create_ticket(client, tokens)
    _set_assignee(client, tokens, ticket["id"], me)
    response = _set_assignee(client, tokens, ticket["id"], None)
    assert response.status_code == 200
    assert response.json()["assignee_id"] is None
    assert response.json()["assignee"] is None


# --- otros roles pueden asignar agentes del mismo tenant --------------------


def test_supervisor_can_assign_agent_of_tenant(client: TestClient) -> None:
    tokens = register_login(client, "sup@example.com", "supervisor", "ten-a")
    target = _user_id(client, register_login(client, "sup-target@example.com", "agent", "ten-a"))
    # El supervisor necesita un ticket: lo crea y se autoasigna una vez.
    ticket = _create_ticket(client, tokens)
    response = _set_assignee(client, tokens, ticket["id"], target)
    assert response.status_code == 200
    assert response.json()["assignee_id"] == target


def test_supervisor_cannot_assign_agent_of_other_tenant(client: TestClient) -> None:
    tokens = register_login(client, "sup-cross@example.com", "supervisor", "ten-a")
    target = _user_id(client, register_login(client, "target-otro@example.com", "agent", "ten-b"))
    ticket = _create_ticket(client, tokens)
    response = _set_assignee(client, tokens, ticket["id"], target)
    assert response.status_code == 404


def test_supervisor_cannot_assign_unknown_user(client: TestClient) -> None:
    tokens = register_login(client, "sup-unk@example.com", "supervisor", "ten-a")
    ticket = _create_ticket(client, tokens)
    response = _set_assignee(client, tokens, ticket["id"], 99999)
    assert response.status_code == 404


def test_supervisor_can_unassign(client: TestClient) -> None:
    tokens = register_login(client, "sup-unassign@example.com", "supervisor", "ten-a")
    ticket = _create_ticket(client, tokens)
    response = _set_assignee(client, tokens, ticket["id"], None)
    assert response.status_code == 200
    assert response.json()["assignee_id"] is None
    assert response.json()["assignee"] is None


# --- GET /v1/agents -------------------------------------------------------


def test_agents_lists_only_active_agents_of_effective_tenants(client: TestClient) -> None:
    sup = register_login(client, "sup-list@example.com", "supervisor", "ten-a")
    agent_a = _user_id(client, register_login(client, "agent-a@example.com", "agent", "ten-a"))
    agent_a2 = _user_id(client, register_login(client, "agent-a2@example.com", "agent", "ten-a"))
    _user_id(client, register_login(client, "agent-b@example.com", "agent", "ten-b"))
    _user_id(client, register_login(client, "sup-b@example.com", "supervisor", "ten-a"))

    # Agente inactivo del tenant (insertado directo, sin membresía).
    with SessionLocal() as db:
        db.add(
            User(
                email="inactivo@example.com",
                password_hash=hash_password("segura-123"),
                role="agent",
                tenant_id="ten-a",
                is_active=False,
            )
        )
        db.commit()

    response = client.get("/v1/agents", headers=_headers(sup))
    assert response.status_code == 200
    agents = response.json()
    ids = [a["id"] for a in agents]
    assert agent_a in ids
    assert agent_a2 in ids
    assert "agent-b@example.com" not in ids
    assert "sup-b@example.com" not in ids
    assert "inactivo@example.com" not in ids
    # Payload completo: id, nombre, mail, rol y estado activo.
    assert all(a.get("is_active") is True for a in agents)
    assert all(a.get("email") and a.get("role") == "agent" for a in agents)


def test_agents_requires_auth(client: TestClient) -> None:
    assert client.get("/v1/agents").status_code == 401


def test_agents_include_legacy_tenant_users(client: TestClient) -> None:
    # Usuarios creados por admin solo tienen users.tenant_id (sin membresía).
    # Deben aparecer igual para el supervisor del tenant.
    sup = register_login(client, "sup-legacy@example.com", "supervisor", "ten-a")
    with SessionLocal() as db:
        legacy = User(
            email="legacy-agent@example.com",
            password_hash=hash_password("segura-123"),
            role="agent",
            tenant_id="ten-a",
            is_active=True,
        )
        db.add(legacy)
        db.commit()
        db.refresh(legacy)
        legacy_id = legacy.id

    response = client.get("/v1/agents", headers=_headers(sup))
    assert response.status_code == 200
    assert legacy_id in [a["id"] for a in response.json()]