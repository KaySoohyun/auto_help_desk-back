# 002 · Autenticación JWT/OAuth — Tareas

_Checklist accionable derivada del `plan.md`. Tareas pequeñas y concretas; marca `[x]` al completarlas._

- [x] Crear `app/core/config.py` con `Settings` (pydantic-settings) leyendo `.env`.
- [x] Crear `app/core/security.py` (hash argon2 + crear/validar JWT con PyJWT).
- [x] Crear modelo `User` (email único, password_hash, role, tenant_id, active).
- [x] Crear modelo `RefreshToken` (jti, user_id, expires_at, revoked).
- [x] Crear schemas Pydantic v2 de auth.
- [x] Crear routers `/auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/me`.
- [x] Crear dependencia `get_current_user` (valida token y resuelve usuario).
- [x] Crear `app/main.py` con la app FastAPI y los routers.
- [x] Escribir tests con pytest: login, refresh, logout, revocación, claims, expiración.
- [x] Actualizar `.env.example`.
- [x] Validar contra los criterios de aceptación de `spec.md`.
- [x] Actualizar `ia_docs/cambios.md` y `roadmap.md`.
- [x] Ejecutar la suite completa y reportar resultados.