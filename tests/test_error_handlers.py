"""Los mensajes de error automáticos de FastAPI se devuelven en español."""

from tests.conftest import register_login


def test_validation_error_in_spanish(client) -> None:
    response = client.post(
        "/auth/register",
        json={"name": "Test Usuario", "email": "no-es-un-email", "password": "corta", "role": "hacker"},
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert isinstance(detail, list)
    msgs = [str(e["msg"]) for e in detail]
    assert any("correo electrónico válido" in m for m in msgs)
    assert any("al menos 8 caracteres" in m for m in msgs)


def test_unknown_route_404_in_spanish(client) -> None:
    response = client.get("/ruta-que-no-existe")
    assert response.status_code == 404
    assert response.json()["detail"] == "No encontrado"


def test_method_not_allowed_in_spanish(client) -> None:
    response = client.put("/health")
    assert response.status_code == 405
    assert response.json()["detail"] == "Método no permitido"


def test_custom_http_exception_keeps_spanish_detail(client) -> None:
    response = client.get("/auth/me", headers={"Authorization": "Bearer token-invalido"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Token inválido"


def test_custom_validator_message_in_spanish(client) -> None:
    tokens = register_login(client, "admin@example.com", "tenant_admin", "ten")
    response = client.patch(
        "/admin/users/999",
        json={},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 422
    assert any("Debe indicar role, is_active o name" in str(e["msg"]) for e in response.json()["detail"])
