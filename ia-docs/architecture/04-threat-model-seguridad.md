# 04 · Threat model y controles de seguridad

> Trazable a `spec.md` §10, §12 y §18. Enfoque: activos, amenazas, controles y verificación.

## 1. Activos a proteger

| Activo | Clasificación | Riesgo si se expone |
|---|---|---|
| Datos de tickets (contenido, historial) | PII CRÍTICA | Fuga de datos de cliente |
| JWT / secrets / claves LLM | Confidencial | Compromiso total de la plataforma |
| Contexto antes de enviar al LLM | PII redactada | Fuga hacia proveedor externo |
| Auditoría / trazabilidad | Regulatorio | Pérdida de evidencias |
| Configuración de tenant | Gobierna políticas | Manipulación de reglas y límites |

## 2. Requisitos de referencia

| Req | Requisito | Fuente |
|---|---|---|
| RS-01 | Validación de JWT en cada request (exp, iss, aud, claims) | spec §10.1 |
| RS-02 | Filtro por tenant obligatorio + RLS recomendado | spec §10.2 |
| RS-03 | RBAC con roles y permisos | spec §10.3 |
| RS-04 | Secrets en vault, rotación, sin secrets en frontend | spec §10.4 |
| RS-05 | TLS en tránsito, cifrado en reposo | spec §10.5 |

## 3. Amenazas y controles

### T1 · Autenticación / JWT

| Riesgo | Detalle | Control | Verificación |
|---|---|---|---|
| Token no validado | Se acepta token sin firma o vencido | Validar firma, exp, iss, aud en cada request (RS-01) | Test: token inválido → 401 |
| Token filtrado / replay | Reutilización cross-sitio | Expiración corta, scope en claims, derivación por usuario+token | Test sobre claims |
| Secret vencido/leakeado | Endurecimiento vía env | Secrets en Vault, sin `.env` en repo, rotación soportada (RS-04) | Revisar config y logs |

### T2 · Acceso cruzado entre tenants

| Riesgo | Detalle | Control | Verificación |
|---|---|---|---|
| tenantA lee data de tenantB | Falta de filtro | Filtro obligatorio por tenant en el repositorio central + RLS (RS-02) | Suite de aislamiento multi-tenant por recurso |
| Ruido en búsqueda | Query sin tenant_id | Cada endpoint valida tenant_id del token y lo compara con el de la URL | Test con tenant de otro valor → 403 |
| Feedback cruzado | feedback de sugerencia de otro tenant | FK + validación de tenant en servicio | Test |

### T3 · Fuga de PII hacia el LLM

| Riesgo | Detalle | Control |
|---|---|---|
| PII en el prompt | password, tarjeta, documento | Redacción previa y tokenización (§9.3) |
| PII en la salida (eco) | El modelo repite datos | Filtro de salida (§12.3) |
| PII en logs | Usuario/ticket crudo en logs operativos | Logs sin payloads crudos; separación logs ops vs audit (§11.3) |

### T4 · Prompt injection y manipulación del LLM

| Riesgo | Detalle | Control |
|---|---|---|
| Ticket inserta instrucciones | Se interpreta como comando de sistema | Ticket siempre como "datos no ejecutables"; delimitar; ignorar instrucciones insertas (§12.1) |
| Cambio de rol / de objetivos | El modelo revela instrucciones o exfiltra | Separación total de instrucciones de sistema vs contenido; validación de salida contra schema |
| Exfiltración de datos | Modelo repite contexto a usuario malicioso | Monitoreo de salida y alertas de contenido bloqueado (§11.1) |

### T5 · Alucinaciones y respuesta incorrecta

| Riesgo | Detalle | Control |
|---|---|---|
| Respuesta inventada (precios, políticas, plazos) | Daño de confianza | Grounding; si no hay fuente → "sin información confiable"; umbral de confianza → revisión humana (FR-08) |
| Envío sin aprobación | Respuesta al cliente sin revisión | Bloqueo de envío automático; aprobación humana obligatoria (FR-04) |
| Acción autónoma | El modelo ejecuta acciones | Las IA solo sugieren acciones; nunca automatización de acciones (§12.2) |

### T5 · Abuso de recursos y abuso de IA

| Riesgo | Detalle | Control |
|---|---|---|
| Uso ilimitado del LLM | Costos inesperados | Rate limit por usuario/ticket/tenant; presupuestos de tokens; monitor (§12.1) |
| Degradación del servicio | LLM caído | Timeout + fallback controlado, no bloquear operación (§12.4) |

## 4. Priorización según spec §18

| Riesgo | Impacto | Mitigación principal | Fase |
|---|---|---|---|
| Fuga de PII | Alto | Redacción + minimización + auditoría | Fase 3 |
| Acceso cruzado tenants | Crítico | Filtro por tenant + RLS | Fases 2-3 |
| Prompt injection | Alto | Delimitación no confiable + filtros | Fase 4 |
| Alucinaciones | Alto | Grounding + confianza + aprobación humana | Fase 4 |
| Respuesta incorrecta | Alto | Edición obligatoria + revisión humana | Fase 5 |
| Dependencia de proveedor LLM | Medio | Fallback, timeouts, operación manual | Fase 4 |
| Costos inesperados | Medio | Límites + monitoreo de tokens | Fase 4 |

## 5. Pruebas de seguridad (Fase 6)

- Suite de aislamiento multi-tenant: verificar recurso por recurso que no hay filtración (§19.2).
- Red team de prompt injection y jailbreak (§19.3).
- SAST/DAST y revisión de dependencias.
- Revisión de firmas JWT (iss, aud, exp, scope) y rotación de secretos.
- Pruebas de cifrado en tránsito (TLS) y en reposo.

## 6. Cifrado y protección de datos (spec §10.4, §10.5)

### 6.1 Cifrado en reposo de campos

- Implementado en `app/core/crypto.py` (feature 004): AES-GCM con clave derivada por HKDF desde `SECRET_KEY`.
- Formato versionado `cipher:<versión>:<salt>:<nonce>:<ct>:<tag>`: cualquier manipulación del dato rompe la autenticación GCM y se rechaza.
- Uso: cifrado selectivo de campos PII críticos (p. ej. descripción de ticket, cuerpo de mensajes) antes de persistir.
- Rotación: cambiar `SECRET_KEY` requiere re-cifrado de los datos con clave anterior (plan de migración) — el versionado permite identificar tokens antiguos.

### 6.2 Cifrado en tránsito

- TLS obligatorio en todos los entornos expuestos (spec §10.5). En desarrollo local no se habilita; en despliegue cloud se termina TLS en el gateway/load balancer.
- No exponer la API sin TLS fuera de localhost; redirigir HTTP → HTTPS en el borde.

### 6.3 Gestión de secretos (spec §10.4)

- MVP: secretos viven en `.env` (nunca versionado) leídos por `pydantic-settings`; `SECRET_KEY` validada con longitud mínima ≥32 (falla el arranque si es corta).
- Plan de migración: mover claves a un vault (HashiCorp Vault / cloud KMS / SSM) con rotación automática; la app lee por interfaz de config, por lo que el cambio no toca el código.
- Reglas: no loggear secretos, no exponer API keys de LLM en frontend, mínimos privilegios por entorno.