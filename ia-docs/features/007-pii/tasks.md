# 007 · Redacción de PII — Tareas

_Checklist accionable derivada del `plan.md`. Tareas pequeñas y concretas; marca `[x]` al completarlas._

- [x] Crear `app/services/pii.py` con reglas de detección (email, teléfono, PAN, DNI/NIE, fecha nacimiento, IP, URL interna) y `PiiRedactor`.
- [x] Crear `app/schemas/pii.py` (request, response, report).
- [x] Crear `app/api/routes_pii.py` con `POST /v1/pii/redact` protegido.
- [x] Registrar router en `app/main.py`.
- [x] Escribir tests de detección y redacción de cada tipo.
- [x] Escribir tests de tokens seguros (sin info del original) y repetición.
- [x] Escribir tests de modos off/detect/redact.
- [x] Escribir tests de no-fuga en auditoría y de permisos (401/403).
- [x] Verificar regresión de la suite completa (**68 tests**, 15 nuevos de PII).
- [x] Validar criterios de aceptación de `spec.md`.
- [x] Actualizar `ia_docs/cambios.md`, `roadmap.md`, `tasks.md` y `spec.md`.
- [x] Ejecutar la suite completa y reportar resultados.

## Notas de implementación

- Detección **no solapada**: `_match_spans` cubre cada posición una sola vez (un span de tarjeta bloquea re-detección por teléfono); spans ordenados por posición.
- Tarjeta con Luhn inválido: se detecta como span pero **no** se redacta (se conserva el original).
- Token `[[PII:TIPO:hash8]]` con salt por request (sha256 truncado); no reversible, sin info del original.
- La firma `redact(text, mode)` no recibe `tenant_id`: la config por tenant quedó diferida (feature 016). Permiso del endpoint usado: `REQUEST_AI_SUGGESTION`.