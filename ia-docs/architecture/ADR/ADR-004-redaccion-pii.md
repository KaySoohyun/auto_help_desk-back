# ADR-004 · Servicio de redacción de PII como capa dedicada

**Estado:** aceptado

## Contexto

El spec exige que la PII se detecte y redacte antes de enviar contenido al LLM (§9.3), con tokens seguros y registro del evento sin exponer el valor original. Esto es crítico (riesgo alto, §18) y debe estar centralizado.

## Decisión

Se implementa un **servicio de redacción de PII dedicado** dentro del backend:

- Detecta campos sensibles (regex + heurística + configuración por tenant) y los reemplaza por tokens seguros aleatorios.
- Registra cada evento de redacción en auditoría **sin el valor original**.
- El mapeo token→original vive **solo en este servicio**, en almacén protegido, y no persiste por defecto (solo por request).
- Es el único punto por el que pasa el contenido antes de llegar al orquestador LLM (ADR-002).

## Alternativas consideradas

- **Redacción en el servicio de tickets** — mezcla responsabilidades y dificulta la auditoría; descartada.
- **Redacción en el orquestador LLM** — el orquestador tendría acceso a datos crudos, rompiendo la separación; descartada.
- **Usar solo regex, sin servicio** — insuficiente para cobertura y trazabilidad; descartado.

## Consecuencias

- Límite claro: el orquestador solo recibe contenido redactado.
- Auditoría de redacción consistente y sin exponer datos originales.
- Pendiente definir (Fase 3) el algoritmo exacto de detección y la configuración por tenant.

## Estado

- [ ] Propuesto
- [x] Aceptado
- [ ] Rechazado

## Referencias

- `spec.md` §9.3, §11, §18.
- `ia_docs/architecture/02-arquitectura-multi-tenant.md` D-03/D-04.
- `ia_docs/architecture/05-politica-pii-retencion.md` §3.