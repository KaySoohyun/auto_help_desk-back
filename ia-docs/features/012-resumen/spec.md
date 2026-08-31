# 012 · Resumen automático de tickets

**Estado:** implementado

## Qué hace

Genera un resumen breve y accionable de un ticket mediante IA (spec §15.2, FR-02, épica 4.3), reutilizando el orquestador LLM (010) y el patrón de la clasificación (011):

- **Entrada**: `ticketId`, `userId` (tenant del token).
- **Contexto**: asunto, descripción e historial de mensajes **redactados** de PII antes de enviarse al LLM (`PiiRedactor`, feature 007).
- **Salida estructurada**: `summary`, `missingInformation`, `confidence`, `warnings`, `traceId` (spec §15.2).
- **Persistencia**: `AISuggestion` con `type='summary'` (misma tabla que 011; ADR-003) en estado `draft`, sin PII en `output`.
- **Límites de confianza (FR-07)**: confianza baja → warnings de revisión humana.
- **Auditoría**: `ai.summarized` con metadata (sin textos); **métricas**: `ai_summaries_total{status}`.

## Por qué

Es el segundo caso de uso de IA (CU-02, complemento de clasificación): el agente debe leer tickets extensos y el resumen le da el contexto en segundos. Sigue exactamente el mismo pipeline seguro que 011 (redacción → orquestador → validación → persistencia → auditoría/métricas).

## Criterios de aceptación

- [ ] `app/services/summarizer.py`: `TicketSummarizer.summarize(ticket_id, user, ...)`:
  - carga ticket + mensajes descifrados del tenant (otro tenant → `PermissionError`);
  - redacta PII del contexto;
  - llama al orquestador con tarea `summary` y prompt versionado;
  - valida salida JSON (`summary` requerido, `missingInformation` opcional, `confidence` en [0,1]);
  - persiste `AISuggestion(type='summary')` draft;
  - audita `ai.summarized` y registra `ai_summaries_total`.
- [ ] Prompt versionado `app/prompts/summary.py` (`SUMMARY_PROMPT_VERSION=1.0.0`) con separación datos/instrucciones (guardrail §12.1).
- [ ] Ruta `POST /v1/ai/tickets/{ticketId}/summary` (`REQUEST_AI_SUGGESTION`): 200 `{summary, missingInformation, confidence, warnings, suggestionId, traceId}`; 404 otro tenant; 429; 503; 422 JSON inválido.
- [ ] Tests: éxito con mock, baja confianza→warnings, otro tenant→404, 401, 503, 422, persistencia sin PII, auditoría y métricas, resumen no incluye PII.
- [ ] Suite completa pasa sin regresión.
- [ ] Docs actualizados.

## Fuera de alcance

- Respuesta sugerida (013), guardrails 014, feedback/workspace 015.
- RAG / base de conocimiento (el resumen usa solo el ticket y su historial).
- Aplicar el resumen al ticket (queda como sugerencia editable).