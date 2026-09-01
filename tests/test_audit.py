from fastapi.testclient import TestClient
from tests.conftest import register_login

from app.database import SessionLocal
from app.models.audit import AuditEvent
from app.services.audit import AuditService


def _events_for(tenant_id: str) -> list[AuditEvent]:
    with SessionLocal() as db:
        return [e for e in db.query(AuditEvent).filter(AuditEvent.tenant_id == tenant_id).all()]


def test_login_success_is_audited(client: TestClient) -> None:
    register_login(client, "ok@example.com", "agent", "ten-1")
    with SessionLocal() as db:
        events = db.query(AuditEvent).all()
    actions = {e.action for e in events}
    assert "auth.user_registered" in actions
    assert "auth.login_success" in actions
    for e in events:
        assert e.trace_id


def test_login_failure_is_audited(client: TestClient) -> None:
    client.post(
        "/auth/register",
        json={"name": "Test Usuario", "email": "fail@example.com", "password": "segura-123", "role": "agent", "tenant_id": "ten-1"},
    )
    client.post("/auth/login", json={"email": "fail@example.com", "password": "incorrecta"})
    with SessionLocal() as db:
        events = db.query(AuditEvent).filter(AuditEvent.action == "auth.login_failed").all()
    assert len(events) == 1
    assert events[0].result == "failure"
    # No contiene PII sensible: no password
    assert "password" not in events[0].detail


def test_audit_events_do_not_contain_passwords(client: TestClient) -> None:
    register_login(client, "no-pii@example.com", "agent", "ten-1")
    with SessionLocal() as db:
        raw = db.query(AuditEvent).all()
    serialized = [str(e.__dict__) for e in raw]
    assert all("segura-123" not in s for s in serialized)


def test_audit_events_paginated_and_tenant_scoped(client: TestClient) -> None:
    register_login(client, "a@example.com", "agent", "ten-a")
    register_login(client, "b@example.com", "agent", "ten-b")

    tokens = register_login(client, "super-a@example.com", "supervisor", "ten-a")
    response = client.get(
        "/audit/events",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
        params={"limit": 50, "offset": 0},
    )
    assert response.status_code == 200
    events = response.json()
    assert len(events) > 0
    # Todos pertenecen a ten-a; los de ten-b no aparecen
    assert all(e["tenant_id"] == "ten-a" for e in events)
    assert not any(e["tenant_id"] == "ten-b" for e in events)


def test_audit_requires_view_audit_permission(client: TestClient) -> None:
    tokens = register_login(client, "agent@example.com", "agent", "ten-1")
    response = client.get(
        "/audit/events",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 403


def test_audit_requires_token(client: TestClient) -> None:
    assert client.get("/audit/events").status_code == 401


def test_audit_service_is_append_only() -> None:
    """El servicio solo ofrece log(); no hay métodos de update/delete."""
    assert not hasattr(AuditService, "delete")
    assert not hasattr(AuditService, "update")


def test_logout_is_audited(client: TestClient) -> None:
    tokens = register_login(client, "logout@example.com", "agent", "ten-1")
    client.post("/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    with SessionLocal() as db:
        events = db.query(AuditEvent).filter(AuditEvent.action == "auth.logout").all()
    assert len(events) == 1
    assert events[0].result == "success"
