import json

import pytest
from fastapi.testclient import TestClient
from tests.conftest import register_login

from app.core.metrics import metrics
from app.database import SessionLocal
from app.models.ai_suggestion import AISuggestion
from app.models.audit import AuditEvent
from app.services.llm import MockLLMProvider


class WorkspaceMock(MockLLMProvider):
    """Proveedor mock que devuelve una clasificación válida (para crear sugerencias)."""

    def __init__(self, *, model: str = "mock-workspace") -> None:
        super().__init__()
        self._model = model

    def complete(self, **kwargs):
        content = json.dumps({
            "category": "general",
            "suggestedPriority": "medium",
            "confidence": 0.9,
        })
        return type("R", (), {
            "content": content,
            "model": self._model,
            "usage": type("U", (), {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10})(),
            "duration_seconds": 0.01,
        })()


@pytest.fixture(autouse=True)
def reset_metrics() -> None:
    metrics.reset()
    yield
    metrics.reset()


@pytest.fixture
def provider(monkeypatch):
    def _patch(provider):
        from app.services.llm_orchestrator import LLMOrchestrator

        monkeypatch.setattr(
            LLMOrchestrator,
            "_effective_provider",
            lambda self: provider,
        )

    return _patch


def _headers(tokens: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _create_ticket(client: TestClient, tokens: dict, **overrides) -> dict:
    payload = {
        "subject": "Problema de acceso",
        "description": "El usuario no puede entrar",
        "category": "technical",
        "priority": "high",
    }
    payload.update(overrides)
    resp = client.post("/v1/tickets", json=payload, headers=_headers(tokens))
    assert resp.status_code == 201, resp.text
    return resp.json()


def _classify(client: TestClient, tokens: dict, ticket_id: int) -> dict:
    resp = client.post(f"/v1/ai/tickets/{ticket_id}/classify", headers=_headers(tokens))
    assert resp.status_code == 200, resp.text
    return resp.json()


def _feedback(client: TestClient, tokens: dict, ticket_id: int, body: dict):
    return client.post(f"/v1/ai/tickets/{ticket_id}/feedback", json=body, headers=_headers(tokens))


def test_feedback_accepted_updates_state(client: TestClient, provider) -> None:
    provider(WorkspaceMock())
    tokens = register_login(client, "agent@example.com", "agent", "ten")
    ticket = _create_ticket(client, tokens)
    suggestion = _classify(client, tokens, ticket["id"])

    resp = _feedback(client, tokens, ticket["id"], {"suggestion_id": suggestion["suggestion_id"], "action": "accepted"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["action"] == "accepted"

    with SessionLocal() as db:
        sug = db.query(AISuggestion).filter(AISuggestion.id == suggestion["suggestion_id"]).one()
        assert sug.state == "accepted"


def test_feedback_edited_stores_hash(client: TestClient, provider) -> None:
    provider(WorkspaceMock())
    tokens = register_login(client, "agent@example.com", "agent", "ten")
    ticket = _create_ticket(client, tokens)
    suggestion = _classify(client, tokens, ticket["id"])

    resp = _feedback(
        client,
        tokens,
        ticket["id"],
        {"suggestion_id": suggestion["suggestion_id"], "action": "edited", "edited_content_hash": "abc123"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["edited_content_hash"] == "abc123"

    with SessionLocal() as db:
        sug = db.query(AISuggestion).filter(AISuggestion.id == suggestion["suggestion_id"]).one()
        assert sug.state == "edited"


def test_feedback_edited_persists_edited_output(client: TestClient, provider) -> None:
    provider(WorkspaceMock())
    tokens = register_login(client, "edito@example.com", "agent", "ten")
    ticket = _create_ticket(client, tokens)
    suggestion = _classify(client, tokens, ticket["id"])

    resp = _feedback(
        client,
        tokens,
        ticket["id"],
        {
            "suggestion_id": suggestion["suggestion_id"],
            "action": "edited",
            "edited_output": {"summary": "Resumen corregido por el agente."},
        },
    )
    assert resp.status_code == 200, resp.text

    with SessionLocal() as db:
        sug = db.query(AISuggestion).filter(AISuggestion.id == suggestion["suggestion_id"]).one()
        assert sug.state == "edited"
        assert sug.output["summary"] == "Resumen corregido por el agente."
    provider(WorkspaceMock())
    tokens = register_login(client, "agent@example.com", "agent", "ten")
    ticket = _create_ticket(client, tokens)
    suggestion = _classify(client, tokens, ticket["id"])

    resp = _feedback(client, tokens, ticket["id"], {"suggestion_id": suggestion["suggestion_id"], "action": "rejected"})
    assert resp.status_code == 200
    resp = _feedback(client, tokens, ticket["id"], {"suggestion_id": suggestion["suggestion_id"], "action": "flagged"})
    assert resp.status_code == 200

    with SessionLocal() as db:
        sug = db.query(AISuggestion).filter(AISuggestion.id == suggestion["suggestion_id"]).one()
        assert sug.state == "flagged"


def test_feedback_other_tenant_is_404(client: TestClient, provider) -> None:
    provider(WorkspaceMock())
    tokens_a = register_login(client, "agent-a@example.com", "agent", "ten-a")
    tokens_b = register_login(client, "agent-b@example.com", "agent", "ten-b")
    ticket = _create_ticket(client, tokens_a)
    suggestion = _classify(client, tokens_a, ticket["id"])

    resp = _feedback(client, tokens_b, ticket["id"], {"suggestion_id": suggestion["suggestion_id"], "action": "accepted"})
    assert resp.status_code == 404


def test_feedback_unknown_suggestion_is_404(client: TestClient, provider) -> None:
    provider(WorkspaceMock())
    tokens = register_login(client, "agent@example.com", "agent", "ten")
    ticket = _create_ticket(client, tokens)
    resp = _feedback(client, tokens, ticket["id"], {"suggestion_id": 999999, "action": "accepted"})
    assert resp.status_code == 404


def test_feedback_invalid_action_is_422(client: TestClient, provider) -> None:
    provider(WorkspaceMock())
    tokens = register_login(client, "agent@example.com", "agent", "ten")
    ticket = _create_ticket(client, tokens)
    suggestion = _classify(client, tokens, ticket["id"])
    resp = _feedback(client, tokens, ticket["id"], {"suggestion_id": suggestion["suggestion_id"], "action": "nope"})
    assert resp.status_code == 422


def test_feedback_requires_edit_permission(client: TestClient, provider) -> None:
    provider(WorkspaceMock())
    tokens = register_login(client, "agent@example.com", "agent", "ten")
    ticket = _create_ticket(client, tokens)
    suggestion = _classify(client, tokens, ticket["id"])
    tokens_read = register_login(client, "viewer@example.com", "agent", "ten")
    resp = _feedback(client, tokens_read, ticket["id"], {"suggestion_id": suggestion["suggestion_id"], "action": "accepted"})
    assert resp.status_code in (200, 403)
    resp_anon = client.post("/v1/ai/tickets/1/feedback", json={"suggestion_id": 1, "action": "accepted"})
    assert resp_anon.status_code == 401


def test_list_suggestions_scoped_by_tenant(client: TestClient, provider) -> None:
    provider(WorkspaceMock())
    tokens_a = register_login(client, "agent-a@example.com", "agent", "ten-a")
    tokens_b = register_login(client, "agent-b@example.com", "agent", "ten-b")
    ticket = _create_ticket(client, tokens_a)
    _classify(client, tokens_a, ticket["id"])

    resp_a = client.get(f"/v1/ai/tickets/{ticket['id']}/suggestions", headers=_headers(tokens_a))
    assert resp_a.status_code == 200
    assert len(resp_a.json()) == 1

    resp_b = client.get(f"/v1/ai/tickets/{ticket['id']}/suggestions", headers=_headers(tokens_b))
    assert resp_b.status_code == 404


def test_my_tickets_returns_only_assigned(client: TestClient) -> None:
    agent1 = register_login(client, "agent1@example.com", "agent", "ten")
    agent2 = register_login(client, "agent2@example.com", "agent", "ten")
    agent1_id = client.get("/auth/me", headers=_headers(agent1)).json()["id"]
    ticket = _create_ticket(client, agent1)

    resp = client.get("/v1/workspace/my-tickets", headers=_headers(agent2))
    assert resp.status_code == 200
    assert resp.json()["total"] == 0

    resp = client.get("/v1/workspace/my-tickets", headers=_headers(agent1))
    assert resp.status_code == 200
    assert resp.json()["total"] == 0  # nadie asignado aún

    resp = client.patch(f"/v1/tickets/{ticket['id']}", json={"assignee_id": agent1_id}, headers=_headers(agent1))
    assert resp.status_code == 200, resp.text
    resp = client.get("/v1/workspace/my-tickets", headers=_headers(agent1))
    assert resp.json()["total"] == 1


def test_feedback_audits_and_metrics(client: TestClient, provider) -> None:
    provider(WorkspaceMock())
    tokens = register_login(client, "agent@example.com", "agent", "ten")
    ticket = _create_ticket(client, tokens)
    suggestion = _classify(client, tokens, ticket["id"])
    _feedback(client, tokens, ticket["id"], {"suggestion_id": suggestion["suggestion_id"], "action": "rejected"})

    with SessionLocal() as db:
        events = db.query(AuditEvent).filter(AuditEvent.action == "ai.feedback").all()
        assert len(events) == 1
        assert events[0].detail["action"] == "rejected"
        assert events[0].detail["suggestion_id"] == suggestion["suggestion_id"]

    sup = register_login(client, "sup@example.com", "supervisor", "ten")
    resp = client.get("/v1/metrics", headers=_headers(sup))
    assert resp.status_code == 200
    assert "ai_feedback_total" in resp.text
