# ADR-005 · Autenticación JWT/OAuth con emisión propia en MVP

**Estado:** aceptado

## Contexto

El spec (§10.1) exige autenticación OIDC/OAuth 2.0 con validación de JWT en cada request, expiración, issuer, audiencia y claims mínimos. En el MVP no hay un IdP externo disponible; hay que decidir cómo emitir/validar los tokens en las fases iniciales.

## Decisión

Para el MVP se implementa **emisión y validación de JWT propios (HS256)** con:

- Claims mínimos: `sub`, `exp`, `iss`, `aud`, `tenant_id`, `roles`, `scopes`.
- Expiración corta (access) + refresh con rotación y revocación.
- Validación estricta de firma, expiración, issuer y audiencia en cada request (middleware).
- Interfaz de autenticación que permita migrar a OIDC/OAuth con IdP externo sin cambiar los endpoints (estándar: el backend sigue validando JWT).

## Alternativas consideradas

- **IdP externo desde el inicio** — depende de infraestructura que no existe aún; se difiere.
- **Sin refresh, solo access de larga duración** — peor seguridad (tokens vencidos más tiempo vivo); descartado.
- **Firma asimétrica (RS256) desde el inicio** — correcto para multi-servicio, pero para un único backend HS256 es suficiente en MVP; se evalúa migrar en Fase 2/3.

## Consecuencias

- Seguridad sólida para MVP sin depender de servicios externos.
- Compatibilidad: cualquier token JWT válido con los claims esperados será aceptado; migrar a OIDC es transparente para los endpoints.
- Requiere gestionar la clave HS256 en vault (RS-04) y rotación.

## Estado

- [ ] Propuesto
- [x] Aceptado
- [ ] Rechazado

## Referencias

- `spec.md` §10.1, §19.2.
- `ia_docs/architecture/04-threat-model-seguridad.md` T1.
- `.env.example` (config de JWT).