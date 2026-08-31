# 06 · Estrategia de IA y guardrails

> Trazable a `spec.md` §12, §15 y §17. Define cómo se estructura la IA para cumplir con calidad, seguridad y métricas.

## 1. Modelos por tarea

| Tarea | Modelo propuesto | Salida | SLA p95 | Fuente |
|---|---|---|---|---|
| Clasificación | LLM pequeño/medio + schema | JSON estructurado | < 2 s | spec §16.1 |
| Resumen | LLM medio + schema | JSON con resumen, missing info | < 5 s | spec §16.1 |
| Respuesta sugerida | LLM medio (grounding KB) + schema | Texto editable + fuentes | < 8 s | spec §16.1 |

> Los modelos concretos quedan por definir en Fase 4 (orquestador). El contrato es: salida estructurada validada.

## 2. Prompts versionados

- Cada tarea tiene una **plantilla de prompt** con versión semver (`v1.0.0`).
- Estructura de la plantilla:
  - **Instrucciones de sistema** (rol y reglas del tenant) — separadas del contenido.
  - **Datos**: ticket redactado, historial, KB si aplica. Marcado como `DATOS_NO_CONFIABLES`.
  - **Reglas de salida**: schema JSON requerido, tono, idioma, límites.
  - **Comportamiento ante falta de datos**: fallback explícito ("sin información suficiente").
- La versión de prompt se guarda en la sugerencia y en auditoría (FR-09, §11.2).
- Cambios de plantilla = nueva versión, no edición in-place.

## 3. Grounding (spec §8 FR-08 y §12.2)

- Si existe KB aprobada por tenant: recuperar artículos (filtro tenant + idioma + vigencia) y pasarlos como contexto, con citas.
- Si no hay fuente suficiente: la salida debe indicar que no tiene información confiable (fallback seguro), NO inventar.
- Se muestran las fuentes usadas en la sugerencia.

## 4. Guardrails de entrada (prompt injection, §12.1)

| Control | Detalle |
|---|---|
| Separación instrucciones/datos | El ticket nunca se mezcla con instrucciones de sistema; se delimita como contenido no ejecutable |
| Ignorar instrucciones insertas | El prompt instruye a no seguir órdenes dentro del contenido del ticket |
| Input validation | Longitud máxima de contexto, tipo esperado |
| Rate limit | Por usuario, ticket y tenant |

## 5. Guardrails de salida (§12.3)

| Control | Detalle |
|---|---|
| Validación de schema | Salida debe parsear al JSON/schema esperado; si no, se rechaza y se registra |
| Filtro de PII | Detectar datos CRÍTICOS en la respuesta y bloquear/redactar |
| Filtro de contenido prohibido | Rechazar instrucciones peligrosas, roles de ataque, etc. |
| Umbral de confianza | Bajo → advertencia visible + sugerir revisión humana (FR-07) |
| Control de tono | Verificar que cumple el tono/config del tenant |

## 6. Control de alucinaciones (§12.2)

- Grounding obligatorio cuando exista KB.
- No afirmar políticas, precios, reembolsos ni compromisos sin evidencia.
- Salida estructurada con campo `grounded_in` o `warnings`.
- Suite de evaluación con dataset de control (regresión de calidad).

## 7. Fallback (§12.4)

| Escenario | Comportamiento |
|---|---|
| LLM timeout/error | Respuesta con error controlado, se registra incidente, se permite operación manual |
| Schema inválido | Reintento limitado; si falla, fallback seguro con aviso |
| Confianza baja | Se entrega pero con advertencia fuerte; nunca se auto-envía |
| Contenido bloqueado | Se muestra "Contenido bloqueado por política de seguridad" |

## 8. Métricas de calidad IA (§17)

| Métrica | Fuente |
|---|---|
| Precisión de clasificación | Comparación vs categoría final del agente |
| Tasa de alucinaciones reportadas | Feedback `flagged` |
| Tasa de respuestas bloqueadas | Guardrails de salida |
| Tasa de baja confianza | Distribución de confianza |
| Aceptación / edición / rechazo | Feedback de agentes (FR-05) |

## 9. Contratos API (resumen del spec §15)

| Endpoint | Método | Descripción |
|---|---|---|
| `/v1/ai/tickets/{ticketId}/classify` | POST | Clasificación sugerida |
| `/v1/ai/tickets/{ticketId}/summary` | POST | Resumen |
| `/v1/ai/tickets/{ticketId}/suggested-reply` | POST | Respuesta sugerida |
| `/v1/ai/tickets/{ticketId}/feedback` | POST | Feedback del agente |

Todos requieren `tenantId`, `userId` y autenticación válida.