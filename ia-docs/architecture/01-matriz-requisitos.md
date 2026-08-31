# 01 · Matriz de requisitos

> Trazable a `spec.md` §5, §6, §8, §9, §10 y §16. Convierte los requisitos del spec en entradas verificables (ID propio) para la fase de pruebas.

## 1. Requisitos funcionales (del spec §8)

| ID | Descripción | Trazabilidad | Verificación |
|---|---|---|---|
| FR-01 | Clasificar tickets con salida estructurada (categoría, subcategoría, intención, prioridad, confianza, motivo) | §8 FR-01 | Esquema válido y persistido |
| FR-02 | Generar resúmenes breves y accionables sin datos innecesarios | §8 FR-02 | Resumen sin PII innecesaria |
| FR-03 | Sugerir respuesta profesional, editable por el agente | §8 FR-03 | Borrador editable |
| FR-04 | Nunca enviar respuesta IA sin aprobación humana | §8 FR-04, §19.1 | Sin envío automático |
| FR-05 | Feedback del agente (útil/editada/rechazada/incorrecta/riesgosa/alucinada) | §8 FR-05 | Feedback persistido y trazado |
| FR-06 | Configuración por tenant (IA on/off, tono, idioma, categorías, escalamiento, KB) | §8 FR-06 | Config tenent independiente |
| FR-07 | Confianza baja → advertencia y sugerir revisión humana | §8 FR-07 | Warning en salida |
| FR-08 | Grounding: priorizar KB aprobada; si no hay fuente, declarar falta de información | §8 FR-08 | Fuentes o "sin info confiable" |
| FR-09 | Trazabilidad de sugerencias (versión prompt, modelo, inputs, salida, estado final) | §8 FR-09 | Data de auditoría completa |
| FR-10 | Consultas optimizadas (tenant, estado, agente, categoría, fecha; contexto IA eficiente) | §8 FR-10 | Satisfacer §16.2 |

## 2. Requisitos de datos (spec §9)

| ID | Descripción | Trazabilidad |
|---|---|---|
| RD-01 | Entrada mínima: ticketId, tenantId, asunto, descripción, historial, estado, categoría/prioridad, metadatos de cliente mínimos, idioma, adjuntos indexables | §9.1 |
| RD-02 | Prohibido enviar al LLM: contraseñas, tokens, credenciales, tarjetas completas, documentos de identidad completos, finanzas sensibles | §9.2 |
| RD-03 | Redacción de PII previa al LLM con tokens seguros y registro del evento | §9.3 |
| RD-04 | Retención configurable por tenant/regulación; sin retención para entrenamiento sin consentimiento | §9.4 |

## 3. Requisitos de seguridad (spec §10)

| ID | Descripción | Trazabilidad |
|---|---|---|
| RS-01 | Autenticación JWT/OAuth obligatoria; validar expiración, issuer, audience, claims | §10.1 |
| RS-02 | Autorización por tenant en cada request; filtro obligatorio por tenant | §10.2 |
| RS-03 | RBAC con roles mínimos y permisos clave | §10.3 |
| RS-04 | Secrets en vault; rotación; no secrets en frontend | §10.4 |
| RS-05 | TLS en tránsito; cifrado en reposo | §10.5 |

## 4. Requisitos de auditoría (spec §11)

| ID | Descripción | Trazabilidad |
|---|---|---|
| RA-01 | Auditar login/acceso, solicitudes IA, decisiones de sugerencia, envío, cambios de config, acceso a auditoría, errores IA y alertas de seguridad | §11.1 |
| RA-02 | Evento mínimo: timestamp UTC, tenantId, userId/service, ticketId, acción, modelo, versión prompt, traceId, resultado, confianza, motivo de bloqueo | §11.2 |
| RA-03 | Integridad de logs; sin PII cruda; investigación forense; separación de logs operativos vs auditoría | §11.3 |

## 5. Requisitos no funcionales (spec §16 y §17)

| ID | Descripción | Métrica / objetivo | Trazabilidad |
|---|---|---|---|
| RN-01 | Latencia clasificación p95 < 2 s | API | §16.1 |
| RN-02 | Latencia resumen p95 < 5 s | API | §16.1 |
| RN-03 | Latencia respuesta sugerida p95 < 8 s | API | §16.1 |
| RN-04 | Disponibilidad ≥ 99.5 % mensual | SLO | §16.1 |
| RN-05 | Índices y paginación obligatoria | Consultas | §16.2 |
| RN-06 | Caché de catálogos/config y contexto corto | Rendimiento | §16.2 |
| RN-07 | Workers asíncronos, colas, rate limits y timeouts | Escalabilidad | §16.3 |
| RN-08 | Métricas de negocio/calidad/seguridad | KPIs | §17 |

## 6. Requisitos regulatorios / riesgos (spec §18)

| ID | Descripción | Responsable |
|---|---|---|
| RG-01 | Prevención de fuga de PII (redacción, minimización, auditoría) | Alto |
| RG-02 | Prompt injection (contenido no confiable, filtros, validación de salida) | Alto |
| RG-03 | Alucinaciones (grounding, confianza, fuentes, aprobación humana) | Alto |
| RG-04 | Respuesta incorrecta (edición obligatoria, revisión humana, feedback) | Alto |
| RG-05 | Acceso cruzado entre tenants (autorización por tenant, pruebas de aislamiento) | Crítico |

> Proyectar: activación de aislamiento (RLS recomendado) y pruebas recorrerán los IDs de esta matriz.