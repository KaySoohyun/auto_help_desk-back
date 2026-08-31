# 004 · Cifrado, secretos y protección de datos — Plan

_Cómo se implementa lo descrito en `spec.md`. Debe respetar la `constitution/`._

## Enfoque

Módulo `app/core/crypto.py` con cifrado simétrico autenticado **AES-GCM** usando `cryptography` (disponible en el venv). La clave se deriva de `SECRET_KEY` mediante HKDF con un salt, de modo que una sola variable de entorno es la fuente de verdad. Salida versionada y verificada al descifrar; cualquier manipulación del token provoca error (detección de tamper). Los secretos siguen llegando de `.env` vía pydantic-settings (como en feature 002); se deja documentado el plan para migrar a Vault.

## Estructura de archivos

```
app/
  core/
    crypto.py           # cifrado/descifrado AES-GCM con formato versionado
    config.py           # (modificar) derivar encryption_key en Settings
tests/
  test_crypto.py        # round-trip, tamperación, clave corta, verificación de advertencias
```

## Implementación

1. Crear `app/core/crypto.py`:
   - `derive_key(master: bytes, salt: bytes) -> bytes` — HKDF-SHA256 para derivar clave de trabajo.
   - `encrypt_field(plaintext: str) -> str` — devuelve `cipher-v1:nonce_base64:ciphertext_base64:tag_base64`.
   - `decrypt_field(token: str) -> str` — valida versión y verifica el tag (integridad + autenticación); lanza error ante token manipulado.
   - Soporte byte (internamente) sin exponer tipos raros en la interfaz de campo.
2. En `app/core/config.py`: validar `secret_key` ≥32 (ya existe) y añadir `encryption_key` derivada de `secret_key` (un solo punto, sin persistirla).
3. Conectar en `TenantScopedRepository` no es obligatorio en esta feature; se deja el helper listo para cifrar campos sensibles en Fase 3 (documentado).
4. Tests en `tests/test_crypto.py`:
   - Round-trip: cifrar → descifrar devuelve el original.
   - El ciphertext no contiene el texto plano (no es legible en claro).
   - Tokens manipulados (cambiar nonce/tag/ct) fallan al descifrar.
   - Clave fuera de formato → error claro.
   - Texto vacío aceptado.
5. Documentar políticas de cifrado en reposo/tránsito y plan de secretos (Vault) en `ia_docs/architecture/04-threat-model-seguridad.md`.
6. Actualizar `.env.example`, `ia_docs/cambios.md`, `roadmap.md`, y spec/tasks de la feature.

## Decisiones

- **AES-GCM** — cifrado autenticado estándar, disponible en `cryptography`; integridad y confidencialidad en un paso. Se descartó ChaCha20-Poly1305 por menor disponibilidad.
- **Clave derivada por HKDF** — una sola fuente (`SECRET_KEY`) con salt; permite rotación cambiando la variable (con plan de re-cifrado documentado).
- **Formato versionado** (`cipher:1:<nonce>:<ct>:<tag>`) — permite migrar algoritmo o clave sin romper datos viejos.
- **Cifrado selectivo por campo**, no TDE — se protegen campos PII puntuales; el cifrado de disco es responsabilidad del storage cloud.
- **Secrets de `.env`** en MVP con la interfaz desacoplada para migrar a Vault/SSM sin tocar la aplicación.

## Riesgos

- **Cambio de SECRET_KEY rompe datos cifrados** — mitigación: documentar plan de re-cifrado/despliegue; el versionado del token (mitiga y permite migración con doble clave).
- **Rendimiento** — AES-GCM sobre strings cortos es imperceptible; no se cifran blobs grandes.
- **Clave en proceso** — mitigación: nunca hardcode de clave, seokrecipes de `.env`/vault; no loggear.