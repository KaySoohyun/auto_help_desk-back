# 002 · Autenticación JWT/OAuth

**Estado:** implementado ✅

## Qué hace

Sistema de autenticación base de la plataforma (Fase 2, épica 2.2 del plan de ejecución). Permite:

- Registrar/crear usuarios de plataforma (admin de plataforma crea admins de tenant).
- Iniciar sesión con email + contraseña y obtener un **access token JWT** corto y un **refresh token** rotativo.
- Validar el token en cada request protegido (firma, expiración, issuer, audiencia, tenant_id y roles).
- Refrescar el access token cuando expira y revocar tokens (logout).
- Estructura preparada para migrar a OIDC/OAuth externo (ADR-005: emisión propia en MVP con HS256).

## Por qué

Es el cimiento de toda la seguridad del spec (§10.1, RS-01). Sin identidad confiable no hay aislamiento por tenant (RS-02) ni RBAC (RS-03) en fases siguientes. El spec y la constitución priorizan "seguridad primero".

## Criterios de aceptación

- [x] `POST /auth/register` permite crear un usuario (con validación de email) solo por admin de plataforma.
- [x] `POST /auth/login` autentica con email+contraseña y devuelve `access_token` + `refresh_token`.
- [x] El access token contiene claims mínimos: `sub`, `exp`, `iss`, `aud`, `tenant_id`, `roles`.
- [x] El access token se valida por firma (HS256), expiración, issuer y audiencia en cada request protegido.
- [x] `POST /auth/refresh` emite un access token nuevo y rota el refresh token.
- [x] `POST /auth/logout` revoca el refresh token (lista de revocación).
- [x] Endpoint protegido de prueba (`/auth/me`) devuelve la identidad del token sin exponer secretos.
- [x] Contraseñas almacenadas con hash seguro (argon2), nunca en texto plano.
- [x] Un token revocado o vencido no puede acceder a rutas protegidas (401/403).
- [x] Test suite con pytest cubre login, refresh, logout, revocación y claims.

## Fuera de alcance

- OIDC/OAuth con proveedor externo (IdP). Solo se deja la interfaz para migrar (ADR-005).
- Gestión de usuarios por tenant (asignación de roles). Va en feature 003 (RBAC).
- Autorización por tenant en endpoints de negocio. Va en feature 003.
- Persistencia avanzada del usuario vía RLS (se implementa en feature 003/006). En esta feature se crea la tabla `users` mínima.
