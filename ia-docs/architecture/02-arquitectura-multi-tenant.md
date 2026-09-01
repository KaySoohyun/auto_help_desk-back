# 02 · Arquitectura cloud multi-tenant

> Trazable a `spec.md` §3, §14 y §16. Sistema: Python/FastAPI, SQLAlchemy 2.x, JWT HS256 propio (PyJWT; OIDC diferido, ADR-005), orquestador LLM con guardrails. Ver contrato en ADR-001.

## 1. Principios rectores

1. **Aislamiento por tenant** en todas las capas (datos, contexto IA, config).
2. **La IA nunca actúa sola**: toda salida es sugerida y auditada.
3. **Datos mínimos al LLM**: redacción de PII antes de la llamada.
4. **Degradación elegante** si el modelo falla; la operación de tickets nunca se bloquea.
5. **Trazabilidad total**: modelo, versión de prompt, trace, confianza y decisión.

## 2. Componentes

```mermaid
flowchart LR
    subgraph Client["Clientes"]
        UI["UI Agente / Admin"]
        API3["Cliente API (service-to-service, client_credentials)"]
    end

    subgraph Edge["Borde"]
        GW["API Gateway / LB"]
        IDP[JWT HS256 propio (PyJWT)]
    end

    subgraph App["Backend (FastAPI)"]
        AUTH["AuthN: validar JWT"]
        TENANT["AuthZ: tenant + RBAC"]
        TICKET["Servicio Tickets"]
        REDAC["Redacción de PII"]
        AUDIT["Servicio Auditoría"]
        FLAG["Salida segura / filtering"]
    end

    subgraph Data["Persistencia (PostgreSQL + RLS)"]
        DB[(tickets, auditoría, config, feedback)]
        CACHE[(Redis: caché catalógicos / rate limit)]
    end

    subgraph AI["Orquestador IA"]
        ORQ[Orquestador LLM]
        EVAL[Control de calidad / schema]
        KB[(Base de conocimiento aprobada)]
        LLM[LLM externo]
        WB[Worker asíncrono]
    end
```

## 2.1. Composición lógica

**Flujo principal (sugerencia de respuesta):**
```
UI Agente → Gateway → JWT HS256 validado
  → Backend: tenant_id validado + RBAC
  → Tickets: leer ticket + historial (contexto mínimo)
  → Redacción PII → contexto seguro (tokens)
  → Orquestador LLM (prompt vX, id)
    · Entrada: contexto redactado + KB aprobada (si aplica)
    · Salida estructurada validada contra schema
  → Filtro de salida (PII/prohibido/peligroso)
  → Auditoría del evento (trace, modelo, versión prompt, confianza)
  → Respuesta al agente (editable, nunca automática)
```

## 3. Roles de cada componente

| Componente | Función | Notas |
|---|---|---|
| API Gateway | TLS, rate limit, rutas | Protege backend |
| JWT HS256 propio | Emisión/validación de JWT (PyJWT); OIDC diferido | usuarios humanos |
| Autenticación JWT | validación token (exp, iss, aud) | §10.1 |
| Autorización | filtro tenant + RBAC | obligatorio siempre |
| Redacción de PII | detectar y tokenizar | §9.3, nunca datos crudos |
| Orquestador LLM | conectar y orquestar llamadas LLM | §14.2 |
| Salida Segura | valida schema/PII/peligrosas | §12.3 |
| Auditoría | registro inmutable de eventos | §11 |
| Workers/colas | clasificación asíncrona, picos | §16.3 |
| Observabilidad | trazas, métricas y alertas | §14.4 |

## 4. Decisiones clave

| # | Decisión | Justificación |
|---|---|---|
| D-01 | API monolítica modulo interna | MVP simple, despliegue único, fácil AI, respetar stack |
| D-02 | Aislamiento por filtro + RLS | RLS recomendado por spec; filtro en ORM obligatorio |
| D-03 | Orquestador único para LLM | abstracción mínima de proveedores, costos controlados |
| D-04 | LLM siempre con input redactado | guardrails de entrada/salida en el orquestador |
| D-05 | Config tenant en DB + caché | controles FR-06 con bajo costo |
| D-06 | Workers async con cola para clasif/resumen | No bloquear la API y mantener SLO |

## 5. Consideración de confidencialidad

- La redacción de PII ocurre en un servicio dedicado, antes de llegar a cualquier capa que envíe a LLM.
- No se envían al LLM: contraseñas, tokens, tarjetas, documentos, finanzas sensibles (§9.2).

## 6. Fuera de alcance (MVP)

No se construye aquí: envío automático, acciones autónomas, multi-idioma avanzado, entrenamiento por tenant, integración multi-provider LLM simultánea (§20.2).