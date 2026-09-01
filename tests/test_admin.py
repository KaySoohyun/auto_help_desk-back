from fastapi.testclient import TestClient
from tests.conftest import register_login

from app.database import SessionLocal
from app.models.audit import AuditEvent
from app.services.audit import AuditService


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _me_id(client: TestClient, tokens: dict) -> int:
    return client.get("/auth/me", headers=_auth(tokens)).json()["id"]


def _events(action: str | None = None) -> list[AuditEvent]:
    with SessionLocal() as db:
        query = db.query(AuditEvent)
        if action:
            query = query.filter(AuditEvent.action == action)
        return list(query.all())


# --- usuarios ---------------------------------------------------------


def test_tenant_admin_creates_user_in_own_tenant(client: TestClient) -> None:
    tokens = register_login(client, "admin@example.com", "tenant_admin", "ten-1")
    resp = client.post(
        "/admin/users",
        json={"name": "Test Usuario", "email": "agent@example.com", "password": "segura-123", "role": "agent", "tenant_id": "ten-1"},
        headers=_auth(tokens),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["role"] == "agent"
    assert body["tenant_id"] == "ten-1"
    assert body["is_active"] is True
    assert "password" not in body


def test_create_user_duplicate_email_409(client: TestClient) -> None:
    tokens = register_login(client, "admin@example.com", "tenant_admin", "ten-1")
    payload = {"email": "dup@example.com", "name": "Test Usuario", "password": "segura-123", "role": "agent", "tenant_id": "ten-1"}
    assert client.post("/admin/users", json=payload, headers=_auth(tokens)).status_code == 201
    resp = client.post("/admin/users", json=payload, headers=_auth(tokens))
    assert resp.status_code == 409


def test_create_user_invalid_role_422(client: TestClient) -> None:
    tokens = register_login(client, "admin@example.com", "tenant_admin", "ten-1")
    resp = client.post(
        "/admin/users",
        json={"name": "Test Usuario", "email": "x@example.com", "password": "segura-123", "role": "hacker", "tenant_id": "ten-1"},
        headers=_auth(tokens),
    )
    assert resp.status_code == 422


def test_tenant_admin_cannot_create_platform_admin(client: TestClient) -> None:
    tokens = register_login(client, "admin@example.com", "tenant_admin", "ten-1")
    resp = client.post(
        "/admin/users",
        json={"name": "Test Usuario", "email": "boss@example.com", "password": "segura-123", "role": "platform_admin"},
        headers=_auth(tokens),
    )
    assert resp.status_code == 403


def test_tenant_admin_cannot_create_in_other_tenant(client: TestClient) -> None:
    tokens = register_login(client, "admin@example.com", "tenant_admin", "ten-1")
    resp = client.post(
        "/admin/users",
        json={"name": "Test Usuario", "email": "x@example.com", "password": "segura-123", "role": "agent", "tenant_id": "ten-2"},
        headers=_auth(tokens),
    )
    assert resp.status_code == 403


def test_platform_admin_creates_user_in_any_tenant(client: TestClient) -> None:
    tokens = register_login(client, "root@example.com", "platform_admin")
    resp = client.post(
        "/admin/users",
        json={"name": "Test Usuario", "email": "admin2@example.com", "password": "segura-123", "role": "tenant_admin", "tenant_id": "ten-9"},
        headers=_auth(tokens),
    )
    assert resp.status_code == 201
    assert resp.json()["tenant_id"] == "ten-9"


def test_platform_admin_requires_tenant_id_for_create(client: TestClient) -> None:
    tokens = register_login(client, "root@example.com", "platform_admin")
    resp = client.post(
        "/admin/users",
        json={"name": "Test Usuario", "email": "x@example.com", "password": "segura-123", "role": "agent"},
        headers=_auth(tokens),
    )
    assert resp.status_code == 422


def test_update_user_role(client: TestClient) -> None:
    tokens = register_login(client, "admin@example.com", "tenant_admin", "ten-1")
    created = client.post(
        "/admin/users",
        json={"name": "Test Usuario", "email": "agent@example.com", "password": "segura-123", "role": "agent", "tenant_id": "ten-1"},
        headers=_auth(tokens),
    ).json()
    resp = client.patch(
        f"/admin/users/{created['id']}",
        json={"role": "supervisor"},
        headers=_auth(tokens),
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "supervisor"


def test_update_user_other_tenant_404(client: TestClient) -> None:
    register_login(client, "admin2@example.com", "tenant_admin", "ten-2")
    tokens = register_login(client, "admin1@example.com", "tenant_admin", "ten-1")
    resp = client.patch("/admin/users/999999", json={"is_active": False}, headers=_auth(tokens))
    assert resp.status_code == 404


def test_cannot_deactivate_self(client: TestClient) -> None:
    tokens = register_login(client, "admin@example.com", "tenant_admin", "ten-1")
    me_id = _me_id(client, tokens)
    resp = client.patch(f"/admin/users/{me_id}", json={"is_active": False}, headers=_auth(tokens))
    assert resp.status_code == 403


def test_deactivate_other_user(client: TestClient) -> None:
    tokens = register_login(client, "admin@example.com", "tenant_admin", "ten-1")
    created = client.post(
        "/admin/users",
        json={"name": "Test Usuario", "email": "agent@example.com", "password": "segura-123", "role": "agent", "tenant_id": "ten-1"},
        headers=_auth(tokens),
    ).json()
    resp = client.patch(f"/admin/users/{created['id']}", json={"is_active": False}, headers=_auth(tokens))
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


def test_user_operations_require_permission(client: TestClient) -> None:
    tokens = register_login(client, "agent@example.com", "agent", "ten-1")
    resp = client.post(
        "/admin/users",
        json={"name": "Test Usuario", "email": "x@example.com", "password": "segura-123", "role": "agent", "tenant_id": "ten-1"},
        headers=_auth(tokens),
    )
    assert resp.status_code == 403


# --- políticas IA por tenant (FR-06) ----------------------------------


def test_tenant_policy_default(client: TestClient) -> None:
    tokens = register_login(client, "admin@example.com", "tenant_admin", "ten-1")
    resp = client.get("/admin/ai-policy", headers=_auth(tokens))
    assert resp.status_code == 200
    assert resp.json()["ai_enabled"] is True
    assert resp.json()["tone"] is None


def test_tenant_policy_save_and_get(client: TestClient) -> None:
    tokens = register_login(client, "admin@example.com", "tenant_admin", "ten-1")
    payload = {
        "ai_enabled": False,
        "tone": "formal",
        "allowed_categories": ["billing", "technical"],
        "escalation_rules": {"max_hours": 24},
    }
    resp = client.put("/admin/ai-policy", json=payload, headers=_auth(tokens))
    assert resp.status_code == 200
    body = resp.json()
    assert body["ai_enabled"] is False
    assert body["tone"] == "formal"
    assert body["allowed_categories"] == ["billing", "technical"]

    resp = client.get("/admin/ai-policy", headers=_auth(tokens))
    assert resp.json()["ai_enabled"] is False
    assert resp.json()["escalation_rules"] == {"max_hours": 24}


def test_tenant_policy_isolation(client: TestClient) -> None:
    t1 = register_login(client, "admin1@example.com", "tenant_admin", "ten-1")
    t2 = register_login(client, "admin2@example.com", "tenant_admin", "ten-2")
    client.put(
        "/admin/ai-policy",
        json={"ai_enabled": False, "tone": "casual", "allowed_categories": ["billing"]},
        headers=_auth(t1),
    )
    resp = client.get("/admin/ai-policy", headers=_auth(t2))
    assert resp.status_code == 200
    assert resp.json()["ai_enabled"] is True
    assert resp.json()["tone"] is None


def test_tenant_policy_requires_permission(client: TestClient) -> None:
    tokens = register_login(client, "agent@example.com", "agent", "ten-1")
    assert client.get("/admin/ai-policy", headers=_auth(tokens)).status_code == 403


def test_tenant_policy_requires_tenant(client: TestClient) -> None:
    tokens = register_login(client, "root@example.com", "platform_admin")
    resp = client.get("/admin/ai-policy", headers=_auth(tokens))
    assert resp.status_code == 403


# --- políticas globales (§4.4) ----------------------------------------


def test_global_policy_defaults(client: TestClient) -> None:
    tokens = register_login(client, "root@example.com", "platform_admin")
    resp = client.get("/admin/ai-policies/global", headers=_auth(tokens))
    assert resp.status_code == 200
    body = resp.json()
    assert body["llm_model"]
    assert body["guardrails_enabled"] is True


def test_global_policy_save_override(client: TestClient) -> None:
    tokens = register_login(client, "root@example.com", "platform_admin")
    resp = client.put(
        "/admin/ai-policies/global",
        json={"llm_model": "gpt-5", "ai_confidence_threshold": 0.7, "guardrails_enabled": False},
        headers=_auth(tokens),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["llm_model"] == "gpt-5"
    assert body["ai_confidence_threshold"] == 0.7
    assert body["guardrails_enabled"] is False

    resp = client.get("/admin/ai-policies/global", headers=_auth(tokens))
    assert resp.json()["llm_model"] == "gpt-5"


def test_global_policy_requires_platform_admin(client: TestClient) -> None:
    tokens = register_login(client, "admin@example.com", "tenant_admin", "ten-1")
    assert client.get("/admin/ai-policies/global", headers=_auth(tokens)).status_code == 403


# --- auditoría con filtros --------------------------------------------


def test_audit_filter_by_action(client: TestClient) -> None:
    tokens = register_login(client, "super@example.com", "supervisor", "ten-1")
    resp = client.get("/audit/events", params={"action": "auth.user_registered"}, headers=_auth(tokens))
    assert resp.status_code == 200
    assert resp.json()
    assert all(e["action"] == "auth.user_registered" for e in resp.json())


def test_audit_filter_by_user_id(client: TestClient) -> None:
    tokens = register_login(client, "super@example.com", "supervisor", "ten-1")
    me_id = _me_id(client, tokens)
    resp = client.get("/audit/events", params={"user_id": me_id, "action": "auth.login_success"}, headers=_auth(tokens))
    assert resp.status_code == 200
    assert resp.json()
    assert all(e["user_id"] == me_id for e in resp.json())


def test_audit_filter_by_result(client: TestClient) -> None:
    tokens = register_login(client, "super@example.com", "supervisor", "ten-1")
    with SessionLocal() as db:
        audit = AuditService(db)
        audit.log("custom.failure", tenant_id="ten-1", service="custom", result="failure")
    resp = client.get("/audit/events", params={"result": "failure"}, headers=_auth(tokens))
    assert resp.status_code == 200
    assert resp.json()
    assert all(e["result"] == "failure" for e in resp.json())


def test_audit_filter_by_date_range(client: TestClient) -> None:
    tokens = register_login(client, "super@example.com", "supervisor", "ten-1")
    resp = client.get(
        "/audit/events",
        params={"date_from": "2099-01-01T00:00:00Z"},
        headers=_auth(tokens),
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_audit_view_is_audited(client: TestClient) -> None:
    tokens = register_login(client, "super@example.com", "supervisor", "ten-1")
    client.get("/audit/events", headers=_auth(tokens))
    assert _events("audit.view")


def test_admin_actions_are_audited(client: TestClient) -> None:
    tokens = register_login(client, "admin@example.com", "tenant_admin", "ten-1")
    created = client.post(
        "/admin/users",
        json={"name": "Test Usuario", "email": "agent@example.com", "password": "segura-123", "role": "agent", "tenant_id": "ten-1"},
        headers=_auth(tokens),
    ).json()
    client.patch(f"/admin/users/{created['id']}", json={"role": "supervisor"}, headers=_auth(tokens))
    client.put(
        "/admin/ai-policy",
        json={"ai_enabled": False, "tone": "formal"},
        headers=_auth(tokens),
    )
    actions = {e.action for e in _events()}
    assert "admin.user_created" in actions
    assert "admin.user_updated" in actions
    assert "admin.tenant_policy_updated" in actions


def test_admin_audit_no_sensitive_data(client: TestClient) -> None:
    tokens = register_login(client, "admin@example.com", "tenant_admin", "ten-1")
    client.post(
        "/admin/users",
        json={"name": "Test Usuario", "email": "agent@example.com", "password": "segura-123", "role": "agent", "tenant_id": "ten-1"},
        headers=_auth(tokens),
    )
    for e in _events("admin.user_created"):
        assert "password" not in e.detail
        assert "segura-123" not in str(e.__dict__)


# --- clientes (consola admin, sin PII) ------------------------------


def test_admin_customers_list_masked_only(client: TestClient) -> None:
    """El admin ve clientes del tenant con email enmascarado, nunca el raw."""
    customer_tokens = register_login(client, "cliente@example.com", "customer", "ten-1")
    assert "access_token" in customer_tokens

    admin_tokens = register_login(client, "admin@example.com", "tenant_admin", "ten-1")
    resp = client.get("/admin/customers", headers=_auth(admin_tokens))
    assert resp.status_code == 200
    customers = resp.json()["items"]
    assert any(c["email_masked"] == "cl***@example.com" for c in customers)
    assert all("email" not in c for c in customers)
    assert all(c["email_masked"] != "cliente@example.com" for c in customers)
    assert all(c["tenant_id"] == "ten-1" for c in customers)


def test_admin_customers_tenant_isolation(client: TestClient) -> None:
    register_login(client, "otro@example.com", "customer", "ten-2")
    admin_tokens = register_login(client, "admin@example.com", "tenant_admin", "ten-1")
    customers = client.get("/admin/customers", headers=_auth(admin_tokens)).json()["items"]
    assert all(c["tenant_id"] == "ten-1" for c in customers)
    assert not any(c["email_masked"] == "ot***@example.com" for c in customers)


def test_admin_customers_requires_admin_role(client: TestClient) -> None:
    agent_tokens = register_login(client, "agent@example.com", "agent", "ten-1")
    assert client.get("/admin/customers", headers=_auth(agent_tokens)).status_code == 403


def test_admin_customers_filter_by_tenant(client: TestClient) -> None:
    register_login(client, "c1@example.com", "customer", "ten-1")
    register_login(client, "c2@example.com", "customer", "ten-2")
    tokens = register_login(client, "admin@example.com", "tenant_admin", "ten-1")
    headers = _auth(tokens)
    # Sin filtro: solo su tenant (ten-1).
    all_customers = client.get("/admin/customers", headers=headers).json()["items"]
    assert all(c["tenant_id"] == "ten-1" for c in all_customers)
    # Filtro explícito a su tenant.
    filtered = client.get("/admin/customers", params={"tenant_id": "ten-1"}, headers=headers)
    assert filtered.status_code == 200
    assert all(c["tenant_id"] == "ten-1" for c in filtered.json()["items"])
    # Filtro a un tenant que no es miembro (sin membresía ni legacy) -> 403.
    denied = client.get("/admin/customers", params={"tenant_id": "ten-2"}, headers=headers)
    assert denied.status_code == 403
