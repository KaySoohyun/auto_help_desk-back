# 011 · Clasificación automática de tickets

**Estado:** implementado

## Qué hace

Permite clasificar un ticket mediante IA con salida estructurada y persistida (spec §15.1, FR-01, épica 4.2), reutilizando el orquestador LLM (feature 010):

- **Entrada**: `ticketId`, `locale`, `userId` (el tenant viene del token, nunca del cliente).
- **Contexto**: asunto, descripción e historial de mensajes **redactados** (PII oculta) antes de enviarse al LLM — se reutiliza `PiiRedactor` (feature 007).
- **Salida estructurada**: `category`, `subcategory`, `intent`, `suggestedPriority`, `confidence`, `rationale`, `warnings`, `traceId` (spec §15.1).
- **Persistencia**: se guarda la clasificación como sugerencia IA en una tabla nueva `ai_suggestions` (ADR-003: sugerencia única con `type='classification'`) con categoría/prioridad sugerida, confianza, modelo, prompt_version y estado.
- **Límites de confianza (FR-07)**: si `confidence` es baja (< umbral configurable), se incluye `warnings` con sugerencia de revisión humana.
- **Auditoría**: `ai.classified` con resultado y metadata (sin textos originales ni salida completa).
- **Métricas**: `ai_classifications_total{status}`, latencia (reutiliza las métricas del orquestador para `llm.*`).

## Por qué

Es el primer caso de uso de IA del sistema (CU-01) y la base de features 012/013. Entrega el contrato §15.1 y habilita que el agente vea una clasificación sugerida revisable.

## Criterios de aceptación

- [ ] Modelo `AISuggestion` (`ai_suggestions`): id, tenant_id, ticket_id, type (`classification|summary|reply`), output (JSON), confidence, model, prompt_version, state (`draft|accepted|rejected`), created_at, updated_at.
- [ ] `app/services/classifier.py`: `TicketClassifier.classify(ticket_id, user)`:
  - carga el ticket + mensajes descifrados;
  - redacta PII del contexto;
  - llama al orquestador con tarea `classify` y prompt versionado (`prompt_version`);
  - parsea y valida el JSON estructurado (si es inválido → `ClassificationError` con fallback seguro);
  - persiste `AISuggestion` (type classification) con estado `draft`;
  - audita `ai.classified` y registra métricas.
- [ ] Ruta `POST /v1/ai/tickets/{ticketId}/classify` (permiso `REQUEST_AI_SUGGESTION`), otro tenant → 404.
  - 200: `{category, subcategory, intent, suggestedPriority, confidence, rationale, warnings, suggestionId, traceId}`.
  - 429 si rate limit; 503 si LLM caído; 422 si JSON inválido (fallback).
- [ ] Categorías/prioridades coherentes con el modelo de tickets (`low|medium|high|urgent`); categorías abiertas pero acotadas a un catálogo mínimo documentado.
- [ ] Umbral de confianza configurable (`ai_confidence_threshold`, default 0.6) → warnings.
- [ ] Tests: clasificación exitosa con mock, baja confianza → warnings, otro tenant → 404, 401/403, LLM caído → 503, JSON inválido → 422, persistencia en `ai_suggestions`, auditoría y métricas, sin PII en la salida ni en auditoría.
- [ ] Suite completa pasa sin regresión.
- [ ] Docs actualizados.

## Fuera de alcance

- Resumen (012) y respuesta sugerida (013) — misma tabla `ai_suggestions`, diferentes tareas.
- Guardrails de entrada/salida avanzados (prompt injection) → feature 014.
- Aceptar/rechazar la sugerencia y feedback del agente (FR-09, §15.4) → feature 015.
- Aplicar la categoría/prioridad al ticket automáticamente (queda como sugerencia editable).
