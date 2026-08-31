# 00 · Casos de uso, roles y flujos

> Trazable a `spec.md` §4, §7 y §14.1.

## 1. Idiomas de referencia

- **CU-01** Clasificación automática de ticket.
- **CU-02** Resumen automático de ticket.
- **CU-03** Sugerencia de respuesta.
- **CU-04** Aceptación o edición de sugerencia.
- **CU-05** Auditoría de IA.

## 2. Catálogo de casos de uso

| ID | Actor | Meta | Disparador | Resultado esperado |
|---|---|---|---|---|
| CU-01 | Sistema (task IA) | Clasificar el ticket | Creación o actualización de ticket | Categoría, subcategoría, intención, prioridad sugerida, confianza y rationale |
| CU-02 | Agente de soporte | Entender rápido el caso | Abre un ticket | Resumen con problema principal, datos relevantes, acciones previas, estado e info faltante |
| CU-03 | Agente de soporte | Redactar respuesta consistente | Solicita respuesta sugerida | Borrador editable con fuentes, confianza y advertencias |
| CU-04 | Agente de soporte | Decidir sobre la sugerencia | Recibe sugerencia IA | Aceptar, editar, rechazar, regenerar o marcar incorrecta/riesgosa |
| CU-05 | Admin de tenant / seguridad | Verificar y auditar actividad IA | Requiere trazabilidad | Registro completo de cada interacción IA con versión de modelo y prompt |

## 3. Flujo de gestión de tickets

```
1. Ticket creado (cliente o API) con metadatos mínimos
2. Tarea asíncrona → CU-01 Clasificación sugerida (con confianza)
3. Agente abre ticket → CU-02 Resumen generado a petición
4. Agente solicita respuesta → CU-03 Borrador sugerido
5. CU-04 El agente acepta / edita / rechaza la sugerencia
6. Aprobación humana obligatoria antes de enviar (FR-04)
7. Envío de respuesta desde flujo humano (no IA)
8. CU-05 Toda acción HA / IA registrada en auditoría
```

## 4. Permisos por rol

_Matriz derivada de `spec.md` §10.3._

| Capacidad | Agente | Supervisor | Admin tenant | Admin plataforma | Servicio IA |
|---|---|---|---|---|---|
| Leer tickets | ✅ | ✅ | ✅ | ✅ (auditoría) | Parcial (contexto redactado) |
| Solicitar clasificación/resumen/respuesta | ✅ | ✅ | — | — | — |
| Editar respuestas | ✅ | ✅ | — | — | — |
| Enviar respuestas | ✅ | ✅ | — | — | — |
| Configurar tenant | — | — | ✅ | — | — |
| Ver auditoría | — | ✅ | ✅ | ✅ | — |
| Gestionar políticas IA globales | — | — | — | ✅ | — |
| Invocar LLM | indirecto | indirecto | indirecto | indirecto | ✅ (exclusivo) |

## 5. Observaciones

- El **Servicio IA** nunca accede a la API de agente para acciones humanas; sólo consume contexto redactado vía servicio interno.
- La decisión de envío final siempre recae en un humano (FR-04, `spec.md` §8).