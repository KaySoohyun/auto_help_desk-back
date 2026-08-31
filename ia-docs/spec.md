# Spec: Agente IA de Soporte

## 1. Nombre del producto / feature
**Agente IA de Soporte para clasificación, resumen y sugerencia de respuestas en tickets.**

## 2. Objetivo
Ayudar a los agentes de soporte a gestionar tickets más rápido y con mayor consistencia mediante un asistente de IA que:
- Clasifica automáticamente tickets.
- Genera resúmenes del problema.
- Sugiere respuestas basadas en contexto y conocimiento aprobado.
- Reduce tiempos de respuesta y errores operativos.
- Mantiene controles estrictos de seguridad, privacidad, auditoría y calidad de IA.

## 3. Alcance

### 3.1 In scope
- Integración del asistente IA dentro del flujo de gestión de tickets.
- Clasificación automática de tickets por categoría, prioridad o intención.
- Generación de resúmenes de tickets.
- Generación de borradores de respuesta para agentes.
- Redacción / enmascaramiento de PII antes de enviar datos al LLM.
- Autorización por tenant y aislamiento de datos.
- Auditoría de acciones humanas y acciones de IA.
- Controles contra prompt injection, fuga de PII y alucinaciones.
- Panel para aceptar, editar o rechazar sugerencias IA.
- Métricas de uso, calidad y feedback.

### 3.2 Out of scope para MVP
- Envío automático de respuestas al cliente sin aprobación humana.
- Entrenamiento de modelos propios por tenant.
- Agentes autónomos que ejecuten acciones irreversibles.
- Soporte multilingüe completo si no está definido en el alcance inicial.
- Integración con canales externos no priorizados.
- Automatización de reembolsos, cambios de cuenta o acciones sensibles sin workflow explícito.

---

# 4. Usuarios y roles

## 4.1 Agente de soporte
- Gestiona tickets diariamente.
- Usa la IA para entender rápido el caso y responder con menor esfuerzo.
- Debe poder editar, aprobar o descartar cualquier sugerencia.

## 4.2 Supervisor / Team Lead
- Revisa calidad de respuestas.
- Consulta métricas de desempeño de IA.
- Detecta casos con errores, alucinaciones o riesgos de cumplimiento.

## 4.3 Administrador de tenant
- Configura usuarios, roles, permisos y políticas del tenant.
- Puede habilitar/deshabilitar funcionalidades IA.
- Consulta auditoría y trazabilidad.

## 4.4 Administrador de plataforma / seguridad
- Supervisa auditoría, acceso, PII y eventos de seguridad.
- Revisa incidentes de prompt injection o fuga de datos.
- Gestiona políticas globales de IA.

---

# 5. Problema a resolver
Los agentes de soporte deben leer tickets extensos, identificar categoría, buscar información relevante y redactar respuestas consistentes. Esto genera:
- Mayor tiempo de respuesta.
- Inconsistencia en respuestas.
- Riesgo de error humano.
- Mayor carga operativa.
- Posibles exposiciones de PII si se copia información a herramientas no controladas.

---

# 6. Propuesta de valor
- Reducir tiempo medio de respuesta.
- Mejorar la consistencia de las respuestas.
- Disminuir esfuerzo cognitivo del agente.
- Aumentar la trazabilidad de la operación.
- Introducir IA con controles de seguridad, privacidad y auditoría.

---

# 7. Casos de uso principales

## CU-01: Clasificación automática de ticket
Cuando se crea o actualiza un ticket, el sistema solicita a la IA una clasificación sugerida:
- Categoría.
- Subcategoría.
- Intención del cliente.
- Prioridad sugerida.
- Nivel de urgencia.

## CU-02: Resumen automático de ticket
El agente abre un ticket y el sistema genera un resumen con:
- Problema principal.
- Datos relevantes.
- Acciones previas.
- Estado actual.
- Información faltante.

## CU-03: Sugerencia de respuesta
El agente solicita una respuesta sugerida. La IA genera un borrador editable basado en:
- Contenido del ticket.
- Historial de conversación.
- Base de conocimiento aprobada, si está disponible.
- Políticas del tenant.
- Restricciones de seguridad y privacidad.

## CU-04: Aceptación o edición de sugerencia
El agente puede:
- Aceptar la sugerencia.
- Editarla antes de enviar.
- Rechazarla.
- Solicitar una nueva versión.
- Marcarla como incorrecta, riesgosa o alucinada.

## CU-05: Auditoría de IA
Cada interacción con la IA queda registrada:
- Usuario que solicitó la acción.
- Tenant.
- Ticket.
- Tipo de acción.
- Modelo y versión.
- Prompt template usado.
- Resultado.
- Nivel de confianza.
- Acción tomada por el agente.

---

# 8. Requisitos funcionales

## FR-01: Clasificación de tickets
El sistema debe permitir clasificar tickets mediante IA con salida estructurada:
- Categoría principal.
- Subcategoría.
- Intención.
- Prioridad sugerida.
- Score de confianza.
- Motivo breve de clasificación.

## FR-02: Resumen de tickets
El sistema debe generar resúmenes breves y accionables.
El resumen no debe incluir datos innecesarios de clientes si no aportan al caso.

## FR-03: Sugerencia de respuesta
El sistema debe generar respuestas sugeridas en tono profesional y alineadas al tenant.
La respuesta siempre debe ser editable por el agente.

## FR-04: Aprobación humana obligatoria
Ninguna respuesta generada por IA debe enviarse automáticamente al cliente en el MVP.
El agente debe aprobar y, si corresponde, editar el contenido antes del envío.

## FR-05: Feedback del agente
El agente debe poder calificar la sugerencia como:
- Útil.
- Editada.
- Rechazada.
- Incorrecta.
- Riesgosa.
- Posible alucinación.

## FR-06: Configuración por tenant
Cada tenant debe poder configurar:
- Activación/desactivación de IA.
- Tono de respuesta.
- Idioma preferido.
- Categorías permitidas.
- Reglas de escalamiento.
- Fuentes de conocimiento aprobadas.

## FR-07: Límites de confianza
Si la confianza del modelo es baja, el sistema debe:
- Mostrar advertencia.
- Sugerir revisión humana.
- Evitar respuestas automáticas o definitivas.

## FR-08: Fuentes y grounding
Cuando exista base de conocimiento, la IA debe priorizar información aprobada.
Si no hay fuente suficiente, debe indicar que no tiene información confiable.

## FR-09: Trazabilidad de sugerencias
Cada sugerencia debe conservar:
- Versión del prompt.
- Versión del modelo.
- Datos de entrada usados.
- Respuesta generada.
- Estado final: aceptada, editada, rechazada.

## FR-10: Búsqueda y optimización de consultas
El sistema debe optimizar consultas recurrentes para:
- Historial de tickets.
- Búsqueda por tenant.
- Consultas por estado, agente, categoría y fecha.
- Carga de contexto para IA sin degradar rendimiento.

---

# 9. Requisitos de datos

## 9.1 Datos de entrada mínimos
- ID del ticket.
- Tenant ID.
- Asunto.
- Descripción.
- Historial de mensajes.
- Estado.
- Categoría actual, si existe.
- Prioridad actual, si existe.
- Metadatos de cliente, solo los necesarios.
- Idioma detectado.
- Adjuntos indexables, si aplica.

## 9.2 Datos prohibidos o minimizados
No se deben enviar al LLM datos innecesarios como:
- Contraseñas.
- Tokens.
- Credenciales.
- Números completos de tarjeta.
- Documentos de identidad completos.
- Información financiera sensible, salvo que sea estrictamente necesaria y esté redactada.

## 9.3 Redacción de PII
Antes de enviar contenido al LLM:
- Se deben detectar y redactar campos sensibles.
- Se deben reemplazar valores por tokens seguros.
- Se debe conservar referencia interna solo si es necesario.
- Se debe registrar el evento de redacción sin exponer el dato original.

## 9.4 Retención
- Los prompts y respuestas deben retenerse según política de auditoría.
- La retención debe ser configurable por tenant y regulación.
- No se deben conservar datos para entrenamiento sin consentimiento explícito y control separado.

---

# 10. Seguridad, identidad y autorización

## 10.1 Autenticación
- Usuarios humanos autenticados vía OIDC / OAuth 2.0.
- Backend debe validar JWT en cada request.
- Tokens deben incluir expiración, issuer, audiencia y claims mínimos.
- Service-to-service communication debe usar OAuth client credentials o mecanismo equivalente.

## 10.2 Autorización por tenant
- Cada request debe incluir tenant validado.
- El sistema debe impedir acceso cruzado entre tenants.
- Las consultas a base de datos deben aplicar filtro obligatorio por tenant.
- Se recomienda row-level security o política equivalente.

## 10.3 RBAC
Roles mínimos:
- Agente.
- Supervisor.
- Admin de tenant.
- Admin de plataforma.
- Servicio IA.

Permisos clave:
- Leer tickets.
- Solicitar sugerencias IA.
- Editar respuestas.
- Enviar respuestas.
- Configurar tenant.
- Ver auditoría.
- Gestionar políticas IA.

## 10.4 Secretos y claves
- API keys de LLM no deben vivir en frontend.
- Secrets gestionados en vault.
- Rotación de claves soportada.
- Acceso mínimo por ambiente.

## 10.5 Cifrado
- TLS obligatorio en tránsito.
- Cifrado en reposo para base de datos, logs y objetos.
- Campos PII con protección adicional si aplica.

---

# 11. Auditoría

## 11.1 Eventos a auditar
- Login y acceso a tickets.
- Solicitud de clasificación IA.
- Solicitud de resumen IA.
- Solicitud de respuesta sugerida.
- Aceptación, edición o rechazo de sugerencia.
- Envío final de respuesta.
- Cambios de configuración del tenant.
- Acceso a auditoría.
- Errores de IA, timeouts y fallbacks.
- Alertas de prompt injection o contenido bloqueado.

## 11.2 Datos mínimos del evento
- Timestamp UTC.
- Tenant ID.
- User ID o service identity.
- Ticket ID.
- Acción.
- Modelo.
- Versión de prompt.
- Trace ID.
- Resultado.
- Nivel de confianza.
- Motivo de bloqueo, si aplica.

## 11.3 Principios
- Logs inmutables o con control de integridad.
- No almacenar PII cruda si no es necesario.
- Permitir investigación forense sin exponer datos sensibles.
- Separación entre logs operativos y logs de auditoría.

---

# 12. Guardrails de IA

## 12.1 Prompt injection
El sistema debe asumir que el contenido del ticket es no confiable.

Controles:
- Separar instrucciones del sistema del contenido del usuario.
- Delimitar contenido del ticket como texto no ejecutable.
- Ignorar instrucciones incrustadas dentro del ticket.
- Bloquear solicitudes que intenten cambiar rol, exfiltrar datos o ejecutar acciones.
- Validar salida contra schema esperado.
- No permitir que el LLM invoque tools sin autorización explícita.
- Aplicar rate limiting por usuario, ticket y tenant.

## 12.2 Alucinaciones
Controles:
- Usar salida estructurada.
- Exigir grounding cuando exista base de conocimiento.
- Mostrar nivel de confianza.
- Si no hay evidencia, responder con fallback seguro.
- Evitar afirmaciones sobre políticas, precios, reembolsos o compromisos si no están verificados.
- Permitir solo acciones sugeridas, no autónomas.
- Evaluar respuestas con dataset de control.

## 12.3 Salida segura
Toda salida IA debe pasar por:
- Validación de schema.
- Filtro de PII.
- Filtro de contenido prohibido.
- Detección de instrucciones peligrosas.
- Verificación de tono y restricciones del tenant.

## 12.4 Fallback
Si el modelo falla:
- Mostrar error controlado.
- Registrar incidente.
- Permitir operación manual.
- No bloquear la gestión completa del ticket.

---

# 13. UX / UI del agente

## 13.1 Panel de ticket
El agente debe ver:
- Datos del ticket.
- Historial.
- Estado.
- Cliente.
- Adjuntos.
- Acciones disponibles.

## 13.2 Panel IA
El panel IA debe mostrar:
- Clasificación sugerida.
- Resumen.
- Respuesta sugerida.
- Nivel de confianza.
- Advertencias.
- Fuentes usadas, si aplica.
- Botones de aceptar, editar, rechazar y regenerar.

## 13.3 Estados
El panel debe manejar:
- Cargando.
- Éxito.
- Error.
- Sin suficiente contexto.
- Bloqueado por seguridad.
- Baja confianza.
- Sugerencia editada.
- Sugerencia rechazada.

## 13.4 Mensajes de advertencia
Ejemplos de estados visibles:
- “Sugerencia generada por IA. Revisar antes de enviar.”
- “Confianza baja. Se recomienda revisión humana.”
- “No se encontró información suficiente en la base de conocimiento.”
- “Contenido bloqueado por política de seguridad.”

---

# 14. Integraciones

## 14.1 Integración con sistema de tickets
- Lectura de ticket.
- Lectura de historial.
- Lectura de metadatos.
- Actualización de categoría/prioridad, si corresponde.
- Guardado de borrador.
- Envío de respuesta desde flujo humano.

## 14.2 Integración con LLM
- API externa o endpoint gestionado.
- Soporte para retries y timeouts.
- Versionado de modelos.
- Selección de modelo por tarea.
- Logging de tokens, latencia y costo si aplica.

## 14.3 Integración con base de conocimiento
- Recuperación de artículos aprobados.
- Filtro por tenant.
- Filtro por idioma.
- Filtro por vigencia.
- Inclusión de citas o referencias.

## 14.4 Integración con observabilidad
- Trazas distribuidas.
- Métricas de latencia.
- Errores.
- Uso de tokens.
- Feedback del agente.
- Alertas de seguridad.

---

# 15. API / contratos sugeridos

## 15.1 Clasificación
`POST /v1/ai/tickets/{ticketId}/classify`

Entrada:
- tenantId
- ticketId
- locale
- userId

Salida:
- category
- subcategory
- intent
- suggestedPriority
- confidence
- rationale
- warnings
- traceId

## 15.2 Resumen
`POST /v1/ai/tickets/{ticketId}/summary`

Entrada:
- tenantId
- ticketId
- userId

Salida:
- summary
- missingInformation
- confidence
- warnings
- traceId

## 15.3 Respuesta sugerida
`POST /v1/ai/tickets/{ticketId}/suggested-reply`

Entrada:
- tenantId
- ticketId
- userId
- tone
- language
- knowledgeBaseIds

Salida:
- suggestedReply
- confidence
- sources
- policyFlags
- warnings
- traceId

## 15.4 Feedback
`POST /v1/ai/tickets/{ticketId}/feedback`

Entrada:
- tenantId
- ticketId
- userId
- suggestionId
- action: accepted | edited | rejected | flagged
- reason
- editedContentHash

---

# 16. Rendimiento y escalabilidad

## 16.1 Objetivos sugeridos
- Clasificación: p95 < 2 segundos.
- Resumen: p95 < 5 segundos.
- Respuesta sugerida: p95 < 8 segundos.
- Disponibilidad mensual objetivo: 99.5% o superior según acuerdo.
- Degradación elegante si LLM no responde.

## 16.2 Optimización de consultas
- Índices por tenant, estado, fecha y categoría.
- Paginación obligatoria.
- Caché para catálogos y configuraciones.
- Caché corta para contexto repetido, respetando privacidad.
- Proyecciones ligeras para lectura de listados.
- Separación entre escrituras transaccionales y procesamiento IA.

## 16.3 Escalabilidad
- Workers asíncronos para clasificación automática.
- Colas para picos de demanda.
- Rate limits por tenant.
- Backpressure y timeouts configurables.

---

# 17. Métricas de éxito

## 17.1 Negocio / operación
- Reducción de tiempo medio de primera respuesta.
- Reducción de tiempo de resolución.
- Aumento de tickets atendidos por agente.
- Tasa de aceptación de sugerencias IA.
- Tasa de edición de sugerencias IA.
- Tasa de rechazo de sugerencias IA.

## 17.2 Calidad IA
- Precisión de clasificación.
- Tasa de alucinaciones reportadas.
- Tasa de respuestas bloqueadas por seguridad.
- Tasa de baja confianza.
- Calidad percibida por agentes.

## 17.3 Seguridad / cumplimiento
- Incidentes de fuga de PII.
- Eventos de prompt injection detectados.
- Errores de autorización por tenant.
- Auditoría completa de acciones IA.
- Tiempo de respuesta ante incidentes.

---

# 18. Riesgos y mitigaciones

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Fuga de PII hacia LLM | Alto | Redacción previa, minimización de datos, auditoría |
| Prompt injection | Alto | Contenido no confiable delimitado, filtros, validación de salida |
| Alucinaciones | Alto | Grounding, confianza, fuentes, aprobación humana |
| Respuesta incorrecta al cliente | Alto | Edición obligatoria, revisión humana, feedback |
| Degradación de rendimiento | Medio | Caché, workers asíncronos, optimización de consultas |
| Acceso cruzado entre tenants | Crítico | Autorización por tenant, RLS, pruebas de aislamiento |
| Dependencia del proveedor LLM | Medio | Fallback, timeouts, degradación manual |
| Costos inesperados | Medio | Límites de uso, monitoreo de tokens, presupuestos |

---

# 19. Criterios de aceptación

## 19.1 Funcionales
- El agente puede generar clasificación, resumen y respuesta sugerida desde un ticket.
- La IA no envía respuestas sin aprobación humana.
- El agente puede aceptar, editar o rechazar sugerencias.
- Las sugerencias muestran confianza y advertencias cuando corresponde.
- El sistema registra feedback del agente.

## 19.2 Seguridad
- Solo usuarios autenticados con JWT/OAuth pueden acceder.
- Un usuario no puede acceder a tickets de otro tenant.
- La PII definida en política se redacta antes de llamar al LLM.
- Todas las acciones IA quedan auditadas.
- Los secrets no están expuestos en frontend ni en logs.

## 19.3 Calidad IA
- La clasificación devuelve esquema válido.
- Las respuestas sin grounding suficiente muestran advertencia.
- Las pruebas de prompt injection bloquean instrucciones no autorizadas.
- Existe suite de evaluación para regresión de calidad.

## 19.4 Rendimiento
- Las consultas principales de tickets cumplen objetivos de latencia.
- La carga de contexto IA no degrada la operación del sistema.
- El sistema soporta picos con colas y degradación controlada.

---

# 20. MVP recomendado

## 20.1 MVP incluye
- Autenticación JWT/OAuth.
- Autorización por tenant.
- API de tickets.
- Clasificación IA.
- Resumen IA.
- Respuesta sugerida editable.
- Redacción básica de PII.
- Auditoría esencial.
- Panel de feedback.
- Guardrails básicos de prompt injection y alucinación.

## 20.2 MVP no incluye
- Envío automático.
- Acciones autónomas.
- Multi-idioma avanzado.
- Entrenamiento personalizado por tenant.
- Analytics predictivo.
- Integraciones con múltiples proveedores LLM simultáneos, salvo abstracción mínima.

---

# 21. Fase posterior sugerida
- Respuestas automáticas de bajo riesgo con políticas estrictas.
- Agentes IA con acciones limitadas y aprobables.
- RAG avanzado con base de conocimiento por tenant.
- Evaluación continua automática.
- Detección proactiva de tickets duplicados.
- Sugerencia de próximos mejores acciones.
- Analítica de calidad por agente y por equipo.
- Soporte multi-idioma completo.
- Enrutamiento inteligente de tickets.