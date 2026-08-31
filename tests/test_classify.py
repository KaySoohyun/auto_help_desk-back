import json

import httpx
import pytest
from fastapi.testclient import TestClient
from tests.conftest import register_login

from app.core.metrics import metrics
from app.database import SessionLocal
from app.models.ai_suggestion import AISuggestion
from app.models.audit import AuditEvent
from app.services.llm import MockLLMProvider


class ClassifyMock(MockLLMProvider):
    """Proveedor mock que devuelve un JSON de clasificación válido."""

    def __init__(self, *, payload: dict | None = None, fail: bool = False, bad_json: bool = False) -> None:
        super().__init__()
        self._payload = payload
        self._fail = fail
        self._bad_json = bad_json

    def complete(self, **kwargs):
        if self._fail:
            raise httpx.TimeoutException("mock timeout")
        if self._bad_json:
            content = "no es json"
        elif self._payload is not None:
            content = json.dumps(self._payload)
        else:
            content = json.dumps(
                {
                    "category": "technical",
                    "suggestedPriority": "high",
                    "confidence": 0.9,
                    "warnings": [],
                }
            )
        return type("R", (), {
            "content": content,
            "model": "mock-classifier",
            "usage": type("U", (), {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20})(),
            "duration_seconds": 0.01,
        })()


@pytest.fixture(autouse=True)
def reset_metrics() -> None:
    metrics.reset()
    yield
    metrics.reset()


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
    resp = client.post("/v1/tickets", json=payload, headers=_headers(tokens))
    assert resp.status_code == 201, resp.text
    return resp.json()


def _classify(client: TestClient, tokens: dict, ticket_id: int):
    return client.post(f"/v1/ai/tickets/{ticket_id}/classify", headers=_headers(tokens))


@pytest.fixture
def classify_provider(monkeypatch):
    """Provee el proveedor mock y lo restaura tras el test (evita fuga global)."""

    def _patch(provider):
        from app.services.llm_orchestrator import LLMOrchestrator

        monkeypatch.setattr(
            LLMOrchestrator,
            "_effective_provider",
            lambda self: provider,
        )

    return _patch


def test_classify_success(client: TestClient, classify_provider) -> None:
    classify_provider(ClassifyMock())
    tokens = register_login(client, "agent@example.com", "agent", "ten")
    ticket = _create_ticket(client, tokens)
    resp = _classify(client, tokens, ticket["id"])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["category"] == "technical"
    assert body["suggested_priority"] == "high"
    assert body["confidence"] == 0.9
    assert body["warnings"] == []
    assert body["suggestion_id"] > 0
    assert body["trace_id"]


def test_classify_requires_token(client: TestClient) -> None:
    assert client.post("/v1/ai/tickets/1/classify").status_code == 401


def test_classify_other_tenant_is_404(client: TestClient, classify_provider) -> None:
    classify_provider(ClassifyMock())
    tokens_a = register_login(client, "agent-a@example.com", "agent", "ten-a")
    tokens_b = register_login(client, "agent-b@example.com", "agent", "ten-b")
    ticket = _create_ticket(client, tokens_a)
    resp = _classify(client, tokens_b, ticket["id"])
    assert resp.status_code == 404


def test_classify_low_confidence_adds_warning(client: TestClient, classify_provider) -> None:
    classify_provider(ClassifyMock(payload={
        "category": "general",
        "suggestedPriority": "low",
        "confidence": 0.3,
        "warnings": [],
    }))
    tokens = register_login(client, "low@example.com", "agent", "ten")
    ticket = _create_ticket(client, tokens)
    resp = _classify(client, tokens, ticket["id"])
    assert resp.status_code == 200
    body = resp.json()
    assert body["confidence"] == 0.3
    assert "revisión humana recomendada: confianza baja" in body["warnings"]


def test_classify_llm_down_returns_503(client: TestClient, classify_provider) -> None:
    classify_provider(ClassifyMock(fail=True))
    tokens = register_login(client, "down@example.com", "agent", "ten")
    ticket = _create_ticket(client, tokens)
    resp = _classify(client, tokens, ticket["id"])
    assert resp.status_code == 503


def test_classify_invalid_json_returns_422(client: TestClient, classify_provider) -> None:
    classify_provider(ClassifyMock(bad_json=True))
    tokens = register_login(client, "bad@example.com", "agent", "ten")
    ticket = _create_ticket(client, tokens)
    resp = _classify(client, tokens, ticket["id"])
    assert resp.status_code == 422


def test_classify_persists_suggestion_without_pii(client: TestClient, classify_provider) -> None:
    classify_provider(ClassifyMock())
    tokens = register_login(client, "persist@example.com", "agent", "ten")
    ticket = _create_ticket(
        client,
        tokens,
        subject="Tarjeta 4111 1111 1111 1111 rota",
        description="Correo cliente@example.com no accede",
    )
    _classify(client, tokens, ticket["id"])
    with SessionLocal() as db:
        suggestions = db.query(AISuggestion).filter(AISuggestion.ticket_id == ticket["id"]).all()
        assert len(suggestions) == 1
        sug = suggestions[0]
        assert sug.type == "classification"
        assert sug.state == "draft"
        assert sug.confidence == 0.9
        assert sug.prompt_version == "1.1.0"
        assert sug.model == "mock-classifier"
        serialized = json.dumps(sug.output)
        assert "4111" not in serialized
        assert "cliente@example.com" not in serialized


def test_classify_success_with_default_mock(client: TestClient) -> None:
    """E2E con el proveedor mock por defecto (sin inyectar): el mock task-aware
    debe devolver JSON que el parser acepte (regresión del 422 en dev)."""
    tokens = register_login(client, "e2e-mock@example.com", "agent", "ten")
    ticket = _create_ticket(client, tokens)
    resp = _classify(client, tokens, ticket["id"])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["category"] == "technical"
    assert body["suggested_priority"] == "high"


def test_classify_audits_and_metrics(client: TestClient, classify_provider) -> None:
    classify_provider(ClassifyMock())
    tokens = register_login(client, "audit@example.com", "agent", "ten")
    ticket = _create_ticket(client, tokens)
    _classify(client, tokens, ticket["id"])

    with SessionLocal() as db:
        events = db.query(AuditEvent).filter(AuditEvent.action == "ai.classified").all()
        assert len(events) == 1
        event = events[0]
        assert event.result == "success"
        assert event.detail["category"] == "technical"
        assert "cliente@example.com" not in str(event.detail)
    text = _render_metrics(client)
    assert "ai_classifications_total" in text


def _render_metrics(client: TestClient) -> str:
    tokens = register_login(client, "sup-metrics@example.com", "supervisor", "ten")
    resp = client.get("/v1/metrics", headers=_headers(tokens))
    assert resp.status_code == 200
    return resp.text