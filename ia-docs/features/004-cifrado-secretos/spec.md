# 004 · Cifrado, secretos y protección de datos

**Estado:** implementado ✅

## Qué hace

Capa de protección de datos en reposo y de gestión segura de secretos (Fase 2, épica 2.4 del plan de ejecución). Sobre el stack existente, agrega:

- **Cifrado en reposo**: valores sensibles de negocio (p. ej. datos PII que se deban proteger adicionalmente, spec §10.5) cifrados con AES-GCM basado en una clave maestra derivada de `SECRET_KEY`.
- **Gestión de secretos**: por MVP los secretos viven en `.env` (no versionado), validados en `Settings`; se deja la interfaz para migrar a Vault/SSM sin tocar el código (RS-04).
- **Protección de datos de acceso**: campos que no deben leerse en claro en la DB (p. ej. tokens de refresh ya están; documentar qué se cifra).
- **Cifrado en tránsito**: TLS obligatorio documentado y habilitable por configuración de deployment (centralizado en docs, no en código de la API).

## Por qué

Es requisito explícito del spec (§10.5) y de la matriz RS-05. El MVP no persiste aún datos de negocio complejos, pero el cimiento de cifrado debe existir antes de que entren tickets con PII (Fase 3). Sin una utilidad de cifrado estándar y repetible, cada feature encriptaría "a su manera" con riesgo de errores.

## Criterios de aceptación

- [x] Existe un módulo de cifrado (`app/core/crypto.py`) con cifrado y descifrado simétrico AES-GCM.
- [x] La clave de cifrado se deriva de la `SECRET_KEY` de configuración (una sola fuente de verdad, nunca hardcodeada).
- [x] El formato cifrado es versionado (`cipher:version:nonce:tag:ct`) y verificado al descifrar (integridad + autenticación).
- [x] `Settings` valida que `SECRET_KEY` exista y tenga longitud mínima (≥32); falla en arranque si no.
- [x] Un helper cifra campos de forma transparente para el repositorio (`encrypt_field` / `decrypt_field`).
- [x] Los secretos (API keys, DB creds) solo se leen de `.env`/variables de entorno; nunca en el código fuente ni en logs.
- [x] Documentación de cifrado en tránsito (TLS) y plan de migración de secretos a Vault.
- [x] Test suite cubre: cifra→descifra round-trip, tamper detection, longitud de clave insuficiente, y que un dato cifrado no sea legible en claro en la DB.

## Fuera de alcance

- Integration con un vault físico real (Vault/SSM/KMS). Solo interfaz y documentación de migración.
- Cifrado de toda la DB (TDE) — se asume cifrado a nivel de storage cloud; aquí se protegen campos sensibles puntuales.
- Gestión de claves con HSM/rotación automática real (se documenta el plan, se implementa en deploy real).
- La API ya usa TLS en deployment; no se añade TLS en el código de desarrollo.