# 004 · Cifrado, secretos y protección de datos — Tareas

_Checklist accionable derivada del `plan.md`. Tareas pequeñas y concretas; marca `[x]` al completarlas._

- [x] Crear `app/core/crypto.py` (derive_key, encrypt_field, decrypt_field).
- [x] Modificar `app/core/config.py` para derivar `encryption_key`.
- [x] Escribir tests de `test_crypto.py` (round-trip, tamperación, clave, texto plano no legible).
- [x] Documentar políticas de cifrado en reposo/tránsito y plan de secretos (Vault) en `architecture/04-threat-model-seguridad.md`.
- [x] Verificar regresión de la suite completa (features 002-003).
- [x] Validar contra los criterios de aceptación de `spec.md`.
- [x] Actualizar `ia_docs/cambios.md`, `roadmap.md`, `tasks.md` y `spec.md`.
- [x] Ejecutar la suite completa y reportar resultados.