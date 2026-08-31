# 014 · Guardrails de IA

**Estado:** implementado

## Qué hace

Centraliza los guardrails de entrada y salida de las llamadas LLM en el orquestador (ADR-002, spec §12, `06-estrategia-ia-guardrails.md` §4-7). Complementa lo ya existente:

**Ya implementado en features previas**
- Separación instrucciones/datos en todos los prompts (011/012/013, §12.1).
- Rate limit por tenant+usuario (010, §12.1).
- Validación de salida JSON contra schema en cada servicio (011/012/013, §12.3).
- Umbral de confianza → warnings de revisión humana (011/012/013, FR-07).
- Fallback seguro ante LLM caído (503) y `LLMUnavailableError` (010, §12.4).

**Nuevo en esta feature**
- **Guardrail de salida en el orquestador** (punto único): antes de devolver `{content, model}`, la salida pasa por filtros y si se bloquea → auditoría + métrica + error controlado que la API mapea a 422 "Contenido bloqueado por política de seguridad" (spec §13.4). No rompe el contrato: el servicio upstream nunca recibe contenido peligroso.
  - **Filtro de PII en salida**: detecta PII CRÍTICA no tokenizada (email, tarjeta, teléfono, DNI/passport, etc.) en la respuesta del LLM (eco de PII, amenaza T3, §12.3). Reutiliza `PiiRedactor` en modo `detect` (007).
  - **Filtro de contenido prohibido**: detecta instrucciones peligrosas/ataque en la salida (cambio de rol, revelar system prompt, exfiltrar, "ignora instrucciones", jailbreak) (§12.1, §12.3).
- **Alerta de prompt injection en entrada**: detecta patrones de instrucciones incrustadas en el contexto del ticket (ya delimitado como `DATOS_NO_CONFIABLES`) y registra evento de auditoría `ai.prompt_injection_alert` sin bloquear la operación (§11.1 "Alertas de prompt injection"; la delimitación del prompt ya protege). Detecta cuando la *salida* pide ignorar/ejecutar.
- **Bloqueo → auditoría y métricas**: evento `ai.blocked` (sin PII) y métrica `ai_guardrail_blocks_total{reason}` (009).

## Por qué

El spec exige guardrails (§12) y la estrategia 06 los ubica en el orquestador. Hoy los guardrails de entrada están dispersos en los prompts y no existe filtro de salida centralizado: un modelo que "ecoee" PII o emita instrucciones peligrosas pasaría sin control. Centralizarlo en el punto único de llamadas (ADR-002) lo hace aplicable a clasificar/resumir/sugerir y a futuras tareas sin duplicar código.

## Criterios de aceptación

- [x] `app/services/guardrails.py`:
  - `GuardrailReport` (dataclass): `blocked: bool`, `reasons: list[str]`.
  - `check_output(content: str) -> GuardrailReport`: detecta PII cruda (vía `PiiRedactor.detect`, 007) y contenido prohibido (patrones de jailbreak/cambio de rol/exfiltración). Si detecta → `blocked=True` con `reasons`.
  - `check_input(content: str) -> GuardrailReport`: detecta patrones de prompt injection en el contexto del ticket (informativo, `blocked=False`).
  - Catálogos de patrones en `app/core/config.py` (`guardrails` habilitados/deshabilitados, lista de patrones).
- [x] `app/services/llm_orchestrator.py`: `complete()` aplica `check_output` antes de devolver; si bloquea → auditoría `ai.blocked` (sin PII) + métrica `ai_guardrail_blocks_total{reason}` + excepción `OutputBlockedError`. Opcionalmente `check_input` al usuario → auditoría `ai.prompt_injection_alert` (no bloquea).
- [x] Mapeo en `app/api/routes_ai.py`: `OutputBlockedError` → 422 "Contenido bloqueado por política de seguridad" (o 200 con warnings según decisión en plan); los endpoints classify/summary/suggested-reply lo capturan.
- [x] Tests `tests/test_guardrails.py`: PII en salida se bloquea; jailbreak en salida se bloquea; salida limpia pasa; salida no-PII no se bloquea; alerta de entrada auditada sin bloquear; métrica y auditoría del bloqueo; endpoints devuelven 422 al bloquear; suite completa sin regresión (`134 passed`).
- [x] Docs actualizados.

## Fuera de alcance

- Suite de evaluación con dataset de control y red teaming (017).
- RAG / base de conocimiento (backlog).
- Modos de tono por tenant (FR-06, fase 5).
- Bloqueo automático de la *entrada* (la delimitación del prompt ya protege; aquí solo se alerta y se audita).
