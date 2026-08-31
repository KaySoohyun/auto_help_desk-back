# 013 · Sugerencia de respuesta editable

**Estado:** implementado

## Qué hace

Genera un borrador de respuesta editable para el agente mediante IA (spec §15.3, FR-03, FR-08, CU-03, épica 4.4), reutilizando el orquestador LLM (010) y el patrón de la clasificación (011) y el resumen (012):

- **Entrada**: `ticketId`, `userId` (tenant del token), `tone` y `language` opcionales.
- **Contexto**: asunto, descripción e historial de mensajes **redactados** de PII antes de enviarse al LLM (`PiiRedactor`, feature 007).
- **Salida estructurada**: `suggestedReply`, `confidence`, `sources`, `policyFlags`, `warnings`, `traceId` (spec §15.3).
- **Persistencia**: `AISuggestion` con `type='reply'` (misma tabla que 011/012; ADR-003) en estado `draft`, sin PII en `output`.
- **Grounding y fuentes (FR-08)**: el prompt exige basar la respuesta solo en el contexto del ticket/historial y declarar las fuentes usadas; si no hay contexto suficiente, la salida debe indicar "sin información confiable" (fallback seguro), no inventar.
- **Límites de confianza (FR-07)**: confianza baja → warnings de revisión humana.
- **Auditoría**: `ai.replied` con metadata (sin textos); **métricas**: `ai_replies_total{status}`.

## Por qué

Es el tercer caso de uso de IA (CU-03): el agente redacta respuestas consistentes y profesionales sin empezar de cero. Sigue exactamente el mismo pipeline seguro que 011/012 (redacción → orquestador → validación → persistencia → auditoría/métricas).

## Criterios de aceptación

- [x] `app/services/reply_suggester.py`: `TicketReplySuggester.suggest_reply(ticket_id, tone, language, ...)`:
  - carga ticket + mensajes descifrados del tenant (otro tenant → `PermissionError`);
  - redacta PII del contexto;
  - llama al orquestador con tarea `reply` y prompt versionado;
  - valida salida JSON (`suggestedReply` requerido, `confidence` en [0,1], `sources` y `policyFlags` opcionales);
  - persiste `AISuggestion(type='reply')` draft;
  - audita `ai.replied` y registra `ai_replies_total`.
- [x] Prompt versionado `app/prompts/reply.py` (`REPLY_PROMPT_VERSION=1.0.0`) con separación datos/instrucciones (guardrail §12.1) y reglas de grounding (FR-08): no inventar políticas/precios/plazos, declarar fuentes.
- [x] Ruta `POST /v1/ai/tickets/{ticketId}/suggested-reply` (`REQUEST_AI_SUGGESTION`): 200 `{suggestedReply, confidence, sources, policyFlags, warnings, suggestionId, traceId}`; 404 otro tenant; 429; 503; 422 JSON inválido.
- [x] Tests: éxito con mock, baja confianza→warnings, otro tenant→404, 401, LLM caído→503, JSON inválido→422, persistencia sin PII, auditoría y métricas, respuesta no incluye PII.
- [x] Suite completa pasa sin regresión (`123 passed`).
- [x] Docs actualizados.

## Fuera de alcance

- Feedback y workspace de agente (015), guardrails 014.
- RAG / base de conocimiento por tenant (el grounding es solo sobre el ticket y su historial).
- Envío automático de la respuesta (la respuesta es editable y el envío es humano, FR-04).
