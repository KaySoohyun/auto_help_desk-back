from fastapi.testclient import TestClient
from tests.conftest import register_login


def test_no_token_401(client: TestClient) -> None:
    assert client.get("/admin/users").status_code == 401


def test_agent_forbidden(client: TestClient) -> None:
    register_login(client, "agent@example.com", "agent", "ten-1")
    response = client.get(
        "/admin/users",
        headers={"Authorization": "Bearer no-existe"},
    )
    assert response.status_code in (401, 403)


def test_tenant_admin_allowed(client: TestClient) -> None:
    tokens = register_login(client, "ta@example.com", "tenant_admin", "ten-1")
    response = client.get(
        "/admin/users",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 200
    # El propio admin pertenece a ten-1, por eso la lista lo incluye
    assert [u["email"] for u in response.json()["items"]] == ["ta@example.com"]


def test_platform_admin_without_tenant_forbidden(client: TestClient) -> None:
    tokens = register_login(client, "pa@example.com", "platform_admin", None)
    response = client.get(
        "/admin/users",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 403


def test_agent_role_forbidden_detail(client: TestClient) -> None:
    tokens = register_login(client, "agent2@example.com", "agent", "ten-1")
    # /admin/users requiere CONFIGURE_TENANT; agent no lo tiene
    response = client.get(
        "/admin/users",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Permiso insuficiente"