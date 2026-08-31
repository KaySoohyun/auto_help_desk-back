# 014 · Guardrails de IA — Plan

_Cómo se implementa lo descrito en `spec.md`._

## Enfoque

Introducir una capa de guardrails dentro del orquestador LLM (punto único, ADR-002) sin romper el contrato `complete() -> {content, model}` ni el pipeline de 011/012/013. Los filtros son deterministas (regex + `PiiRedactor.detect`) y no dependen de otro LLM.

## Implementación

1. **`app/services/guardrails.py`**:
   - `OutputBlockedError(ValueError)`.
   - `GuardrailReport` (dataclass): `blocked: bool`, `reasons: list[str]`.
   - `Guardrails` (sin estado, inyectable):
     - `check_output(content: str) -> GuardrailReport`:
       1. PII: `PiiRedactor().redact(content, mode="detect")` → si `report.total > 0` y hay tipos CRÍTICOS → `blocked=True`, reason `pii_leak`.
       2. Prohibido: iterar `settings.guardrail_prohibited_patterns` (regex) sobre el contenido → si match, `blocked=True`, reason `prohibited_content`.
       3. Devuelve report.
     - `check_input(content: str) -> GuardrailReport`: itera `settings.guardrail_injection_patterns` (regex de instrucciones incrustadas) → devuelve report con `blocked=False` y `reasons` informativos.
   - Config `app/core/config.py`: `guardrails_enabled: bool = True`, `guardrail_prohibited_patterns: list[str]` (default: jailbreak/cambio de rol/exfiltración/ignora instrucciones), `guardrail_injection_patterns: list[str]` (default: "ignora instrucciones", "system prompt", "exfiltra", etc.).

2. **`app/services/llm_orchestrator.py`**:
   - Inyectar `guardrails: Guardrails | None = None`; default `Guardrails()`.
   - En `complete()`, tras obtener `response` (éxito):
     - `check_output(response.content)` → si `blocked`:
       - métrica `ai_guardrail_blocks_total{reason=...}` (una por reason).
       - auditoría `ai.blocked` (sin contenido, solo `reason` y `task`).
       - lanzar `OutputBlockedError("Contenido bloqueado por política de seguridad")`.
     - Opcional: `check_input(user)` antes de la llamada → si hay `reasons`, auditoría `ai.prompt_injection_alert` con `reasons` (sin bloquear).
   - Si `guardrails_enabled` es False → saltar filtros (feature flag para desplegar).

3. **Mapeo en `app/api/routes_ai.py`**:
   - Importar `OutputBlockedError`.
   - En classify/summary/suggested-reply (y ping): `except OutputBlockedError → 422` con detail "Contenido bloqueado por política de seguridad".
   - Nota: la decisión de 422 (bloqueo duro) cumple §12.3/§13.4. Alternativa "200 con warnings" se descarta: una salida con PII/prohibido no debe llegar al agente.

4. **Tests `tests/test_guardrails.py`**:
   - `GuardrailMock` (proveedor con contenido configurable).
   - Inyección vía `monkeypatch` sobre `_effective_provider` (mismo fixture que classify/summary).
   - Casos:
     - salida con email/tarjeta → 422 y bloqueo.
     - salida con "ignore your instructions / system prompt reveal" → 422.
     - salida limpia → 200 (regresión con `SummaryMock`/`ReplyMock`).
     - alerta de entrada (ticket con "ignora instrucciones") → operación sigue, evento `ai.prompt_injection_alert` en auditoría.
     - métrica `ai_guardrail_blocks_total` presente tras un bloqueo.
     - `guardrails_enabled=False` → no bloquea (monkeypatch de settings).
     - test unitario directo de `Guardrails.check_output/check_input`.

## Riesgos

- **Falsos positivos en regex**: los patrones se mantienen conservadores (frases típicas de jailbreak/exfiltración); se revisan en 017 (red team). Si un falso positivo aparece, se ajusta el patrón (versión).
- **Ruptura del contrato del orquestador**: `OutputBlockedError` se propaga como excepción; todos los endpoints lo mapean a 422. Los tests verifican que los casos limpios no cambian.
- **Over-engineering**: no se añade segundo LLM evaluador ni modelos de clasificación; regex + `PiiRedactor` cubren el MVP y la evaluación formal llega en 017.
- **PII en la salida legítima**: el prompt de 013 ya instruye a no repetir datos del cliente; el filtro es una red de seguridad, no la primera barrera.
