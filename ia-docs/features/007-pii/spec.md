# 007 · Redacción de PII

**Estado:** implementado (pendiente merge a develop)

## Qué hace

Servicio de detección y redacción de PII (ADR-004, Fase 3, épica 3.3 del plan de ejecución) que protege el contenido de tickets —y su historial— **antes de cualquier uso externo** (envío a LLM, exportaciones). Implementa la política §3 de `ia_docs/architecture/05-politica-pii-retencion.md` y el requisito RD-03 del spec.

- **Detección** de datos sensibles con regex + heurística sobre texto libre (subject, description, body de mensajes y metadatos libres).
- **Redacción** de los valores detectados reemplazándolos por tokens seguros; la lista de tipos prohibidos al LLM es la de spec §9.2 (RD-02).
- **Auditoría** de cada evento de redacción **sin el valor original** (solo acción, servicio, tipos redactados y trace_id).
- Configuración básica por tenant del comportamiento del redactor (nivel off/solo-detección/redactar) según spec FR-06.

## Por qué

Es un requisito de seguridad P0 y RD-03/RS-05. Sin esta capa, el contenido cifrado en reposo (feature 006) viajaría **crudo** al orquestador LLM (feature 010 en Fase 4), violando el spec §9.3 y el ADR-004. Debe implementarse ahora porque la Fase 4 consume este pipeline.

## Criterios de aceptación

- [x] Existe un servicio `PIIRedactionService` que atraviesa textos y reemplaza ocurrencias de tipos sensibles por tokens.
- [x] Tipos detectados como mínimo: correo electrónico, teléfono, tarjeta (PAN), DNI/NIE, fecha de nacimiento, IP. (URL interna incluida; lista ampliable — ver plan.)
- [x] El token es seguro: no contiene información del valor original; formato `[[PII:TIPO:hash]]`.
- [x] `redact(text, mode)` devuelve texto tokenizado + `PIIReport` (tipos detectados y conteos).
- [x] El valor original **nunca** se registra en auditoría ni en logs; el evento solo contiene tipos/conteos + trace_id.
- [x] `PIIReport`/`PIIRedactResponse` no exponen valores en claro a través de la API.
- [x] Existe endpoint de prueba protegido (`POST /v1/pii/redact`, RBAC) que aplica redacción a un input y devuelve el resultado.
- [x] Tests: detección de cada tipo, redacción de múltiples ocurrencias, idempotencia, ausencia de valores originales en auditoría, permisos (401).
- [x] Modos por request `off | detect | redact` con default `redact`.

## Fuera de alcance

- Redacción de adjuntos binarios/PDFs (se marca como backlog; MVP es texto).
- Mapeo token→original reversible persistente (decisión: mapeo por request en memoria, sin persistencia, §05 política).
- Integración con el orquestador LLM (feature 010): aquí solo el motor + endpoint de prueba.
- Reglas de retención/anonymización automática de datos antiguos (feature de gobernanza posterior).
- Cifrado (ya resuelto en feature 006).