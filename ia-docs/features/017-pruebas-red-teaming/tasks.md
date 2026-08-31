# 017 · Pruebas y red teaming — Tareas

_Checklist accionable derivada del `plan.md`._

- [x] `tests/datasets/__init__.py` — paquete de datasets.
- [x] `tests/datasets/redteam.py` — `INJECTION_PAYLOADS` (6 payloads, 5 efectos: rol_change, exfiltration, reveal_prompt, embedded_instructions, jailbreak).
- [x] `tests/datasets/classification.py` — `CLASSIFICATION_CASES` (7 tickets de control) + `MockClassifyProvider` por caso.
- [x] `tests/test_redteam.py`:
  - [x] Parametrizado `test_injection_payloads_do_not_execute_or_leak` (sin fuga de PII, auditoría `alert`, bloqueo 422 si el LLM coopera).
  - [x] `test_classify_ticket_of_other_tenant_404` y `test_suggestions_of_other_tenant_404`.
  - [x] `test_rate_limit_exceeded_429` (respuesta esperada + auditoría `rate_limited`).
- [x] `tests/test_ia_evaluation.py`:
  - [x] Parametrizado `test_classification_matches_dataset` (FR-01).
  - [x] `test_low_confidence_warning` (FR-07).
  - [x] `test_reply_without_sources_has_warning` (FR-08).
  - [x] `test_no_hallucination_when_no_grounding`.
- [x] `tests/test_performance.py` (épica 6.3):
  - [x] Fixture `query_counter` (evento `after_cursor_execute` en el engine para contar queries del request).
  - [x] `test_list_does_not_load_deferred_description` (sin campo `description` en el listado).
  - [x] `test_list_emits_bounded_queries` (número fijo/bajo de queries, sin N+1).
  - [x] `test_pagination_respects_limits` (exactamente `limit` items y `total` correcto).
  - [x] `test_total_count_with_filters` (total con filtro `status` correcto).
- [x] Ejecutar suite completa sin regresión (`200 passed`; baseline `171 passed` + 29 nuevos).
- [x] Actualizar `ia_docs/cambios.md`, `roadmap.md` (017 a Hecho, Fase 6 parcial) y spec/plan/tasks.

## Notas

- Feature de verificación: no se modifica código de producto; si un test revela un bug, se documenta y se propone corrección aparte.
- Evaluación IA con mock provider; el dataset queda listo para proveedor real (se documenta).
- Rendimiento mide patrón de consultas (queries emitidas), no latencia absoluta (inestable en CI).
- Reutiliza patrones de `tests/test_guardrails.py`, `tests/test_workspace.py` y el conftest (`register_login`, `clean_db`).
