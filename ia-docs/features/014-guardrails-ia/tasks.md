# 014 · Guardrails de IA — Tareas

_Checklist accionable derivada del `plan.md`._

- [x] `app/services/guardrails.py`: `OutputBlockedError`, `GuardrailReport`, `Guardrails.check_output()` (PII detect + patrones prohibidos) y `check_input()` (patrones de prompt injection).
- [x] Config `app/core/config.py`: `guardrails_enabled`, `guardrail_prohibited_patterns`, `guardrail_injection_patterns`.
- [x] `app/services/llm_orchestrator.py`: aplicar `check_output` (bloquea → auditoría `llm.call` blocked + métrica `ai_guardrail_blocks_total`) y `check_input` (alerta `llm.call` alert, sin bloquear).
- [x] `app/api/routes_ai.py`: mapear `OutputBlockedError` → 422 "Contenido bloqueado por política de seguridad" en classify/summary/suggested-reply/ping.
- [x] Tests `tests/test_guardrails.py`: bloqueo por PII en salida, bloqueo por jailbreak en salida, salida limpia pasa (200), alerta de entrada auditada sin bloquear, métrica y auditoría del bloqueo, `guardrails_enabled=False`, tests unitarios de `Guardrails`.
- [x] Ejecutar suite completa sin regresión (`134 passed`).
- [x] Actualizar `ia_docs/cambios.md`, `roadmap.md` y spec/plan/tasks.

## Notas

- Punto único de guardrails en el orquestador (ADR-002); los prompts ya separan instrucciones/datos (011-013).
- Filtros deterministas (regex + `PiiRedactor`); sin segundo LLM; la evaluación formal (dataset de control) llega en 017.
- La salida bloqueada nunca llega al agente: 422 con mensaje de política de seguridad (spec §13.4).
