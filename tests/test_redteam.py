"""Red teaming de prompt injection (spec §12.1, épica 6.4, feature 017).

Prueba los endpoints IA reales contra el dataset `tests/datasets/redteam.py`:
verifica que la inyección en el ticket NO se ejecuta, que la salida no filtra PII
ni contenido prohibido, que la inyección se audita (`llm.call` con `alert`) y que
el guardrail de salida bloquea si el LLM "coopera" devolviendo contenido peligroso.
"""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from tests.conftest import register_login
from tests.datasets.redteam import INJECTION_PAYLOADS

from app.core.rate_limit import rate_limit_store
from app.database import SessionLocal
from app.models.audit import AuditEvent
from app.services.llm import LLMResponse, LLMUsage
from app.services.llm_orchestrator import LLMOrchestrator


class EchoProvider:
    """Devuelve el contenido exacto recibido (simula un LLM 'cooperando' con el ataque)."""

    def complete(self, *, messages, model, max_tokens, temperature=0, task=None) -> LLMResponse:
        user_content = messages[-1]["content"] if messages else ""
        return LLMResponse(
            content=user_content,
            model=model,
            usage=LLMUsage(prompt_tokens=10, completion_tokens=10),
            duration_seconds=0.01,
        )


class CleanClassifyProvider:
    """Devuelve una clasificación válida y limpia (sin PII ni contenido prohibido)."""

    def complete(self, *, messages, model, max_tokens, temperature=0, task=None) -> LLMResponse:
        content = json.dumps({
            "category": "general",
            "suggestedPriority": "medium",
            "confidence": 0.9,
        })
        return LLMResponse(
            content=content,
            model=model,
            usage=LLMUsage(prompt_tokens=10, completion_tokens=10),
            duration_seconds=0.01,
        )


@pytest.fixture(autouse=True)
def reset_global_state() -> None:
    rate_limit_store.reset()
    yield
    rate_limit_store.reset()


@pytest.fixture
def patch_provider(monkeypatch):
    def _patch(provider):
        monkeypatch.setattr(LLMOrchestrator, "_effective_provider", lambda self: provider)

    return _patch


def _headers(tokens: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _create_ticket(client: TestClient, tokens: dict, description: str) -> int:
    resp = client.post(
        "/v1/tickets",
        json={
            "subject": "Ticket de prueba",
            "description": description,
            "category": "general",
            "priority": "medium",
        },
        headers=_headers(tokens),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _classify(client: TestClient, tokens: dict, ticket_id: int):
    return client.post(f"/v1/ai/tickets/{ticket_id}/classify", headers=_headers(tokens))


def _llm_alerts(tenant_id: str) -> list[AuditEvent]:
    with SessionLocal() as db:
        return list(
            db.scalars(
                select(AuditEvent).where(
                    AuditEvent.action == "llm.call",
                    AuditEvent.tenant_id == tenant_id,
                    AuditEvent.result == "alert",
                )
            ).all()
        )


@pytest.mark.parametrize("payload", INJECTION_PAYLOADS, ids=lambda p: p["expected_effect"])
def test_injection_payloads_do_not_execute_or_leak(
    client: TestClient, patch_provider, payload
) -> None:
    tokens = register_login(client, "agent@example.com", "agent", "ten")
    patch_provider(CleanClassifyProvider())
    ticket_id = _create_ticket(client, tokens, payload["description"])

    resp = _classify(client, tokens, ticket_id)
    assert resp.status_code == 200, resp.text

    body = resp.json()
    # La salida no repite la instrucción maliciosa ni filtra el payload
    assert payload["description"] not in json.dumps(body)

    # La inyección queda auditada como alerta (no bloquea, pero se registra)
    assert _llm_alerts("ten")


@pytest.mark.parametrize("payload", INJECTION_PAYLOADS, ids=lambda p: p["expected_effect"])
def test_blocked_output_when_llm_cooperates(client: TestClient, patch_provider, payload) -> None:
    tokens = register_login(client, "agent@example.com", "agent", "ten")
    patch_provider(EchoProvider())
    ticket_id = _create_ticket(client, tokens, payload["description"])

    resp = _classify(client, tokens, ticket_id)
    assert resp.status_code == 422
    assert "política de seguridad" in resp.json()["detail"]


def test_classify_ticket_of_other_tenant_404(client: TestClient) -> None:
    tokens_a = register_login(client, "a@example.com", "agent", "ten-a")
    tokens_b = register_login(client, "b@example.com", "agent", "ten-b")
    ticket_id = _create_ticket(client, tokens_a, "Problema de facturación")

    resp = client.post(f"/v1/ai/tickets/{ticket_id}/classify", headers=_headers(tokens_b))
    assert resp.status_code == 404


def test_suggestions_of_other_tenant_404(client: TestClient) -> None:
    tokens_a = register_login(client, "a@example.com", "agent", "ten-a")
    tokens_b = register_login(client, "b@example.com", "agent", "ten-b")
    ticket_id = _create_ticket(client, tokens_a, "Problema de facturación")

    resp = client.get(f"/v1/ai/tickets/{ticket_id}/suggestions", headers=_headers(tokens_b))
    assert resp.status_code == 404


def test_rate_limit_exceeded_429(client: TestClient, patch_provider, monkeypatch) -> None:
    from app.core.config import settings as app_settings

    monkeypatch.setattr(app_settings, "llm_rate_max_calls", 2)
    tokens = register_login(client, "agent@example.com", "agent", "ten")
    patch_provider(CleanClassifyProvider())
    ticket_id = _create_ticket(client, tokens, "Problema de facturación")

    assert _classify(client, tokens, ticket_id).status_code == 200
    assert _classify(client, tokens, ticket_id).status_code == 200
    resp = _classify(client, tokens, ticket_id)
    assert resp.status_code == 429

    with SessionLocal() as db:
        events = db.scalars(
            select(AuditEvent).where(
                AuditEvent.action == "llm.call",
                AuditEvent.tenant_id == "ten",
                AuditEvent.result == "rate_limited",
            )
        ).all()
    assert events
