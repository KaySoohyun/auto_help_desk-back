# 002 · Autenticación JWT/OAuth — Plan

_Cómo se implementa lo descrito en `spec.md`. Debe respetar la `constitution/`._

## Enfoque

Backend FastAPI modular, estructurado para crecer en Fase 2/3 sin refactor grande. Se usa el stack real instalado: `PyJWT` para tokens, `passlib[argon2]` para hash de contraseñas, `pydantic-settings` para configuración desde `.env`, SQLAlchemy 2.x para la tabla `users` mínima. Todo validado con `pytest` + `httpx`.

## Estructura de archivos

```
app/
  main.py            # FastAPI app + inclusión de routers
  core/
    config.py        # Settings (pydantic-settings) desde .env
    security.py      # hash/verify contraseña + create/validate JWT
    deps.py          # dependencias FastAPI (get_current_user, etc.)
  models/
    user.py          # modelo SQLAlchemy User
    token.py         # modelo SQLAlchemy RefreshToken (revocación)
  schemas/
    auth.py          # Pydantic: LoginRequest, TokenResponse, UserOut, ...
  api/
    routes_auth.py   # /auth/* endpoints
tests/
  conftest.py        # cliente de prueba + DB SQLite temporal
  test_auth.py       # tests de login/refresh/logout/revocación/claims
```

## Implementación

1. `app/core/config.py` — `Settings` con `secret_key`, expiraciones, algoritmo, issuer, audience, `database_url`. Cargado desde `.env`.
2. `app/core/security.py` — `hash_password` / `verify_password` (passlib+argon2); `create_access_token`, `create_refresh_token`, `decode_token` (PyJWT, validando exp/iss/aud).
3. `app/models/user.py` — `User` (id, email único, password_hash, role, tenant_id, active, created_at).
4. `app/models/token.py` — `RefreshToken` (id, jti, user_id, expires_at, revoked) para revocación.
5. `app/schemas/auth.py` — schemas Pydantic v2 (LoginRequest, TokenResponse, RefreshRequest, UserOut).
6. `app/api/routes_auth.py` — endpoints `/auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/me`.
7. `app/core/deps.py` — dependencia `get_current_user` que valida el access token y resuelve el usuario.
8. `tests/` — suite de pytest con DB SQLite en memoria y cliente httpx.
9. Actualizar `.env.example`, `ia_docs/cambios.md` y `roadmap.md`.

## Decisiones

- **Emisión propia con HS256 en MVP** — ADR-005; migración a OIDC transparente (los endpoints siguen validando JWT estándar).
- **argon2 para hash** — más seguro que bcrypt/sha; disponible en venv (`argon2-cffi`).
- **Refresh token rotativo con `jti` y revocación** — cumple "revocación" del AGENTS.md y del spec §10.1; se guarda en DB para poder invalidar.
- **Tabla `users` mínima sin RBAC** — RBAC completo en feature 003; aquí solo `role` como string.
- **No cifrar tokens, solo firmar** — JWT no se cifra en MVP (HS256); se evita poner datos sensibles como claims.

## Riesgos

- **Clave secreta débil** — mitigación: `.env.example` con placeholder y **validación de longitud mínima (≥ 32 chars)** en config que impide arrancar con clave corta.
- **Dependencias no disponibles** — mitigación: verificado con `pip freeze` (PyJWT, passlib, argon2-cffi instalados).
- **Tokens vencidos con manejo confuso** — mitigación: **401 diferenciado** (expirado vs inválido) + tests dedicados.
- **Revocación incompleta** — mitigación: refresh token en DB + chequeo de `revoked` en cada uso; **logout solo revoca el refresh token**, el access expira solo (15 min).