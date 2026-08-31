# 007 · Redacción de PII — Plan

_Cómo se implementa lo descrito en `spec.md`. Respeta la `constitution/` y el ADR-004._

## Enfoque

Motor de redacción **sin dependencias externas** (stdlib `re` + heurística). Cada tipo PII tiene una regla; el servicio recorre el texto, reemplaza las ocurrencias por tokens seguros, produce un `PIIReport` y registra auditoría **sin valores originales**. Se expone un endpoint protegido de prueba. La configuración por tenant queda diferida; el modo se acepta por request con default `redact`.

## Estructura de archivos

```
app/
  services/
    pii.py              # PiiRedactor + PIIReport + reglas PII
  schemas/
    pii.py              # PIIRedactRequest, PIIRedactResponse, PIIReportOut
  api/
    routes_pii.py       # POST /v1/pii/redact (protegido)
tests/
  test_pii.py           # detección, redacción, tokens, auditoría, permisos, modos
```

## Implementación

1. `app/services/pii.py`:
   - Enumeración de tipos: `email`, `phone`, `card`, `pan`, `id_number` (DNI/NIE/NIF), `passport`, `birth_date`, `ip_address`, `internal_url`.
   - `PIIReport`: `types: dict[str, int]` (conteo por tipo) y `total: int`.
   - `PIIRedactor.redact(text, mode="redact") -> RedactedResult`:
     - `off` → devuelve el texto sin cambios.
     - `detect` → reemplaza y marca `redacted=true`, no persiste nada.
     - `redact` → reemplaza por tokens.
     - Cada tipo usando regex:
       - email: `[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}`
       - phone: digits con `+`, `-`, espacios, 7-15 dígitos.
       - card/PAN: 13-19 dígitos (permite separadores) + validación Luhn.
       - id_number: patrón DNI/NIE español y passports genéricos.
       - birth_date: `\d{1,2}/\d{1,2}/(19|20)\d{2}`
       - ip_address: IPv4 e IPv6 completa.
       - internal_url: URLs con dominio interno/localhost (heurística).
   - Token: `[[PII:TIPO:<hash8>]]`, `hash8` = `sha256(valor + salt_request)[:8]`; sin información del valor original.
2. `app/schemas/pii.py` — `PIIRedactRequest(text: str, mode: PIIMode = "redact")`, `PIIRedactResponse(text: str, report: PIIReportOut)`, `PIIReportOut(types: dict[str,int], total: int)`.
3. `app/api/routes_pii.py`:
   - `POST /v1/pii/redact` — protegido con `require_permissions(REQUEST_AI_SUGGESTION)` (borrador de contexto IA).
   - Audita `pii.redacted` con `trace_id`; `detail` solo contiene tipos/conteos, **nunca** el texto.
4. Registrar router en `app/main.py`.
5. Tests `tests/test_pii.py`: detección por tipo, múltiples ocurrencias, modos, token sin info del original, repetición, no-PII en auditoría, 401/403, `subject` no expuesto.
6. Actualizar `ia_docs/cambios.md`, `roadmap.md`, spec/tasks.

## Decisiones

- **`re` stdlib** — sin dependencias nuevas (regla de AGENTS/tech-stack).
- **Token basado en hash, no reversible** — no hay mapeo token→original persistente (§05: por request). `salt` por request impide precomputation.
- **Endpoint separado** — el motor queda disponible para Fase 4; se integra en el pipeline del orquestador LLM (feature 010).
- **Config tenant diferida** — se acepta `mode` por request; la configuración por tenant se hará en feature 016 de administración.
- **`REQUEST_AI_SUGGESTION` como permiso del endpoint** — representa quién puede preparar contexto para IA. Si el spec pide otro permiso, se ajusta.

## Riesgos

- **Falsos positivos de regex** → threshold de longitud mínimo y Luhn para tarjetas; lista ampliable.
- **Detección incompleta** → se acepta cobertura incremental; el motor queda extensible por reglas.
- **Fuga de valor en auditoría/logs** → testes que garantizan que `detail` y logs no contienen original; el servicio nunca loggea `text`.
- **Romper features previas** → regresión completa de la suite.