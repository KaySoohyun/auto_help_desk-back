# 017 · Pruebas y red teaming

**Estado:** hecho

## Qué hace

Primera feature de Fase 6 (épicas 6.1-6.4). Convierte en suite ejecutable y parametrizable las garantías de seguridad, privacidad, rendimiento y calidad de IA que ya se implementaron en 002-016, usando dataset de control y pruebas de red teaming sobre los endpoints reales. No añade funcionalidad de producto; añade verificación formal.

- **Red teaming de prompt injection (§12.1, épica 6.4)**: dataset de payloads de ataque (cambio de rol, exfiltración de datos, revelar system prompt, instrucciones incrustadas, jailbreak) inyectados en el campo de descripción del ticket, probados contra los endpoints IA reales. Verifica que: la salida no se ejecuta, la salida no filtra PII del ticket, la inyección se audita (`llm.call` con `alert`), y el guardrail de salida bloquea si el LLM "coopera" devolviendo contenido peligroso.
- **Pruebas de seguridad y privacidad (§19.2, épica 6.2)**: matriz de acceso cruzado multi-tenant sobre endpoints IA (sugerencias/clasificación de otro tenant → 404/403), ausencia de fuga de PII en respuestas IA y en auditoría (redacción previa al LLM, §9.3), y validación de rate limit por tenant+usuario (010).
- **Pruebas de rendimiento (§16, épica 6.3)**: verificación sobre el patrón de consultas de los listados: la carga de un listado paginado NO dispara la columna diferida `description` (feature 008) ni consultas N+1 por ticket, el conteo total con filtros es correcto, y la paginación respeta límites. Se mide cantidad de queries emitidas (no latencia real, inestable en CI) y tamaño de proyección.
- **Evaluación de IA con dataset de control (§17.2, épica 6.4)**: suite de casos de clasificación con salida esperada (categoría/intención/prioridad) y confianza, verificando: estructura de salida válida (FR-01), advertencia por confianza baja (FR-07), grounding/warnings en respuesta sugerida sin fuentes (FR-08), y ausencia de alucinaciones en casos sin información suficiente.

## Por qué

El spec §19 define criterios de aceptación de seguridad y calidad que hasta ahora solo se verifican con casos aislados en cada feature. La 017 los consolida en una suite de evaluación y red teaming reutilizable y documentada (épica 6.4 del plan de ejecución), que es la base para el pipeline de CI de la 018 y para medir regresión de calidad de IA.

## Criterios de aceptación

- [ ] `tests/datasets/redteam.py` — `INJECTION_PAYLOADS: list[dict]`: cada payload con `description`, `expected_effect` (rol_change | exfiltration | reveal_prompt | embedded_instructions | jailbreak) y `expect_blocked_output`.
- [ ] `tests/datasets/classification.py` — `CLASSIFICATION_CASES: list[dict]`: tickets de control con `category`, `intent`, `suggested_priority` y `description` esperados, para evaluar la salida del clasificador.
- [ ] `tests/test_redteam.py`:
  - [ ] Test parametrizado: por cada payload de inyección, crear ticket con la descripción maliciosa y llamar a `/v1/ai/tickets/{id}/classify` (y `/suggested-reply`); la salida NO filtra PII del ticket ni datos de sistema (si se detecta fuga → 422 por guardrails); el evento `llm.call` con `result="alert"` queda auditado.
  - [ ] Test de cooperación del LLM: con proveedor mock que devuelve contenido prohibido/PII, el endpoint responde 422 y bloquea (reutiliza patrón de `test_guardrails.py`).
  - [ ] Test de aislamiento: clasificar/sugerir sobre ticket de otro tenant → 404; listar sugerencias de otro tenant → 404.
  - [ ] Test de rate limit: exceder `llm_rate_max_calls` → 429 o `LLMRateLimitExceeded` manejado (según contrato existente en 010) y auditar `result="rate_limited"`.
- [ ] `tests/test_ia_evaluation.py`:
  - [ ] Test parametrizado sobre `CLASSIFICATION_CASES`: la salida del clasificador tiene schema válido (FR-01) y `category`/`intent` coinciden con el esperado del dataset (con mock provider configurado por caso).
  - [ ] Test de confianza baja (FR-07): salida con `confidence < ai_confidence_threshold` → warning de revisión humana presente.
  - [ ] Test de grounding (FR-08): respuesta sugerida sin fuentes → `policyFlags`/`sources` vacío y warning indicando falta de información confiable.
  - [ ] Test de no alucinación: caso sin información suficiente → salida no afirma hechos no verificados (proveedor mock devuelve respuesta con `sources: []`).
- [ ] `tests/test_performance.py` (épica 6.3):
  - [ ] `test_list_does_not_load_deferred_description`: tras crear tickets, listar con `GET /v1/tickets` y verificar (vía contador de queries o acceso a columnas) que `description` (diferida) no se carga en el listado.
  - [ ] `test_list_emits_bounded_queries`: el listado paginado emite un número fijo y bajo de queries (sin N+1 por ticket), independiente del tamaño de la página.
  - [ ] `test_pagination_respects_limits`: `limit`/`offset` devuelven exactamente `limit` items y el `total` es correcto.
  - [ ] `test_total_count_with_filters`: `GET /v1/tickets?status=...` reporta `total` correcto con filtros (coincide con el conteo real).
- [ ] Docs: `ia_docs/features/017-pruebas-red-teaming/` con plan de pruebas (spec.md, plan.md, tasks.md) y resultados resumidos en `ia_docs/cambios.md`.
- [ ] Suite completa sin regresión (171 + nuevos).

## Fuera de alcance

- Pruebas de carga reales y latencia p95 en producción (se requiere entorno con base de datos/red representativa; los tests miden patrón de consultas, no latencia absoluta).
- Pentesting manual y plan de remediación formal (requiere entorno externo; se documenta como actividad, no código).
- Evaluación con LLM real en CI (usa mock provider; el dataset queda listo para ejecución con proveedor real).
- Feature flags, rollout y dashboards (018).
