# ADR-001 · Aislamiento por tenant con filtro central obligatorio

**Estado:** aceptado

## Contexto

El sistema es multi-tenant y el spec exige que ningún usuario acceda a datos de otro tenant (RS-02, §10.2). Hay que decidir el mecanismo de aislamiento que se implementará en el backend (SQLAlchemy 2.x).

## Decisión

Se implementa **filtro por tenant centralizado en el repositorio (capa de datos)** como mecanismo obligatorio, y se habilita **Row-Level Security (RLS)** en la base de datos como capa de defensa en profundidad.

- Toda consulta y escritura a tablas con `tenant_id` pasa por el repositorio, que inyecta `WHERE tenant_id = :current_tenant` (nunca desde el call site).
- El `tenant_id` se obtiene del JWT validado, nunca de inputs del cliente.
- RLS en PostgreSQL se activa como red de seguridad (aunque falle el ORM, la DB filtra).
- Tests de aislamiento recorren recurso por recurso (spec §19.2).

## Alternativas consideradas

- **Esquemas separados por tenant** — más aislamiento, pero complejidad alta de migraciones y pool; descartada para MVP.
- **Solo RLS** — sin filtro en el ORM la app no es portable ni testeable en SQLite; descartado.
- **Solo filtro en endpoints** — fácil de olvidar; descartado en favor del repositorio central.

## Consecuencias

- Aislamiento fuerte y testeable; los desarrolladores no pueden saltarse el filtro por olvido.
- Requiere que todos los modelos con tenant_id pasen por el repositorio (invariante del proyecto).
- La capa de datos se vuelve la frontera de autorización; si se añade una tabla nueva hay que registrarla aquí.

## Estado

- [ ] Propuesto
- [x] Aceptado
- [ ] Rechazado

## Referencias

- `spec.md` §10.2 (RS-02), §19.2.
- `ia_docs/architecture/03-modelo-datos-pii.md` §3.
- `ia_docs/architecture/04-threat-model-seguridad.md` T2.