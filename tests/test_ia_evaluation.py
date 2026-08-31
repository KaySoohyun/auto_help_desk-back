"""Evaluación de IA con dataset de control (spec §17.2, FR-01, FR-07, FR-08, épica 6.4).

Verifica con el dataset `tests/datasets/classification.py` (mock provider
determinista) que el clasificador produce una salida válida y coherente, que la
confianza baja genera advertencia de revisión humana (FR-07) y que la sugerencia
de respuesta sin fuentes no alucina (FR-08, grounding limitado al ticket).
"""

import json

import pytest
from fastapi.testclient import TestClient
from tests.conftest import register_login
from tests.datasets.classification import CLASSIFICATION_CASES, MockClassifyProvider

from app.core.rate_limit import rate_limit_store
from app.services.llm import LLMResponse, LLMUsage
from app.services.llm_orchestrator import LLMOrchestrator


class MockReplyProvider:
    """Devuelve una respuesta sugerida sin fuentes (FR-08): no inventa hechos."""

    def __init__(self, *, reply: str, confidence: float, warnings: list[str]) -> None:
        self._reply = reply
        self._confidence = confidence
        self._warnings = warnings

    def complete(self, *, messages, model, max_tokens, temperature=0, task=None) -> LLMResponse:
        content = json.dumps({
            "suggestedReply": self._reply,
            "confidence": self._confidence,
            "sources": [],
            "policyFlags": ["información no verificable"],
            "warnings": self._warnings,
        })
        return LLMResponse(
            content=content,
            model=model,
            usage=LLMUsage(prompt_tokens=10, completion_tokens=10),
            duration_seconds=0.01,
        )


@pytest.fixture(autouse=True)
def reset_rate_limit() -> None:
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


def _create_ticket(client: TestClient, tokens: dict, subject: str, description: str) -> int:
    resp = client.post(
        "/v1/tickets",
        json={
            "subject": subject,
            "description": description,
            "category": "general",
            "priority": "medium",
        },
        headers=_headers(tokens),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.mark.parametrize(
    "index", range(len(CLASSIFICATION_CASES)), ids=lambda i: CLASSIFICATION_CASES[i]["expected_category"]
)
def test_classification_matches_dataset(client: TestClient, patch_provider, index) -> None:
    case = CLASSIFICATION_CASES[index]
    tokens = register_login(client, f"agent{index}@example.com", "agent", "ten")
    patch_provider(MockClassifyProvider(index=index))
    ticket_id = _create_ticket(client, tokens, case["subject"], case["description"])

    resp = client.post(f"/v1/ai/tickets/{ticket_id}/classify", headers=_headers(tokens))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Schema válido (FR-01) y coherente con el caso de control
    assert body["category"] == case["expected_category"]
    assert body["suggested_priority"] == case["expected_priority"]
    assert body["confidence"] > 0
    assert body["suggestion_id"] > 0
    assert body["trace_id"]


def test_low_confidence_warning(client: TestClient, patch_provider) -> None:
    tokens = register_login(client, "agent@example.com", "agent", "ten")
    patch_provider(MockClassifyProvider(index=0, confidence=0.3))
    ticket_id = _create_ticket(client, tokens, "No llega la factura", "El cliente no recibió su factura mensual.")

    resp = client.post(f"/v1/ai/tickets/{ticket_id}/classify", headers=_headers(tokens))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["confidence"] == 0.3
    assert any("confianza baja" in w.lower() or "revisión humana" in w.lower() for w in body["warnings"])


def test_reply_without_sources_has_warning(client: TestClient, patch_provider) -> None:
    tokens = register_login(client, "agent@example.com", "agent", "ten")
    patch_provider(MockReplyProvider(
        reply="Hola, para poder ayudarte necesitamos más información sobre tu caso.",
        confidence=0.4,
        warnings=["información insuficiente para confirmar los detalles"],
    ))
    ticket_id = _create_ticket(client, tokens, "Consulta", "El cliente pide información de su pedido.")

    resp = client.post(f"/v1/ai/tickets/{ticket_id}/suggested-reply", headers=_headers(tokens))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Sin fuentes (grounding limitado, FR-08) y con advertencia de revisión humana
    assert body["sources"] == []
    assert body["warnings"]
    assert any("confianza baja" in w.lower() or "revisión humana" in w.lower() for w in body["warnings"])


def test_no_hallucination_when_no_grounding(client: TestClient, patch_provider) -> None:
    tokens = register_login(client, "agent@example.com", "agent", "ten")
    patch_provider(MockReplyProvider(
        reply="No contamos con información suficiente para confirmar precios o plazos. Solicito más detalles.",
        confidence=0.3,
        warnings=["no se encontró información suficiente en la base de conocimiento"],
    ))
    ticket_id = _create_ticket(client, tokens, "Consulta de precio", "El cliente pregunta por un precio.")

    resp = client.post(f"/v1/ai/tickets/{ticket_id}/suggested-reply", headers=_headers(tokens))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # No inventa hechos: sin fuentes, sin afirmación verificada y con advertencia
    assert body["sources"] == []
    assert "precio" not in body["suggested_reply"].lower().split("confirmar")[0]
    assert any(w for w in body["warnings"])
