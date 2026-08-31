# 05 · Política de PII, retención y minimización

> Trazable a `spec.md` §9.2, §9.3, §9.4 y §11.

## 1. Principios

1. **Minimización**: el sistema recoge solo los datos necesarios para operar el ticket (spec §9.1). Nada accesorio al propósito.
2. **Redacción antes del LLM**: ningún dato CRÍTICO viaja crudo al modelo (spec §9.3).
3. **Retención por política** y por tenant, no por defecto infinito (spec §9.4).
4. **No uso para entrenamiento** sin consentimiento explícito y control separado.

## 2. Datos prohibidos al LLM (lista completa, spec §9.2)

Nunca se envían al LLM aunque el contexto los contenga:

- Contraseñas y tokens de sesión.
- Credenciales, claves API.
- Números completos de tarjeta (PAN).
- Documentos de identidad completos (DNI/passport/NIE).
- Información financiera sensible, salvo que sea estrictamente necesaria y vaya redactada.
- Datos internos de acceso (URLs de admin, endpoints internos, identificadores de infraestructura).

## 3. Redacción (spec §9.3)

Flujo obligatorio antes de cualquier llamada a IA:

```
Ticket crudo
  → Detectar campos sensibles (regex + heurística + lista por tenant)
  → Reemplazar valor por token seguro (ej.: [[PII:CN:digito_final]])
  → Conservar referencia interna solo si es necesario (mapeo reversible en servicio redactor, no en LLM)
  → Registrar evento de redacción SIN el valor original (§11) 
  → Contexto tokenizado → orquestador LLM
```

- El mapeo token→original vive **solo dentro del servicio de redacción**, en almacén protegido (nada de mapeo en logs).
- Los tokens se generan con aleatoriedad y no deben contener información del dato original.

## 4. Retención (spec §9.4)

| Dato/tipo | Retención por defecto | Configuración tenant | Nota |
|---|---|---|---|
| Tickets + historial | 24 meses | Regulable (6-48) | Según acuerdo y regulación |
| Sugerencias IA + resultado | 24 meses | Regulable | Se requiere para auditoría AI (FR-09) |
| Auditoría / eventos | 5 años | Fijo (append-only) | Integridad e investigación |
| Logs operativos | 30 días | No ampliable | Separado de auditoría |
| Mapeo token→PII (redacción) | Corto: 1 sesión de IA | No persistido como default | Solo si referencia interna |

> Valores a confirmar con el usuario: son propuestos, no definitivos.

## 4. Clasificación de retención por reglas

- Los datos de tickets se borran/anonimizan al terminar el período de retención del tenant.
- No se conserva nada para entrenamiento salvo consentimiento explícito y botón separado (opt-in con contrato).
- Cuando un tenant se elimina (offboarding), se purgan sus tickets y config; la auditoría mínima (sin PII) puede retenerse por regulación.

## 5. Reglas para logs y auditoría

- Nunca loggear contenido del ticket ni tokens de intercambio PII.
- En los eventos de auditoría se conserva sólo la huella (trace_id, hash de referencia si aplica, ver pendientes en `03-modelo-datos-pii.md`).
- Registros mutables están prohibidos en la tabla de auditoría (append-only, spec §11.3).

## 6. Decisiones pendientes

- Hash/anonimización del email del usuario en auditoría.
- Valores de retención exactos por reglamento (por confirmar).
- ¿Token mapping temporal persistente o por request? **Propuesto: por request sin persistencia** — requiere OK.