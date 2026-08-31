# Runbook · Rollback

_Volver a una versión estable tras un release defectuoso._

## Decisión

Solo aplicar rollback si el problema **no** se resuelve con un hotfix rápido o con el kill-switch (ver abajo). Si el defecto es de IA, preferir el kill-switch: es instantáneo y no redime el resto del tráfico.

## Procedimiento con kill-switch (IA defectuosa, 1 minuto)

1. Poner `AI_FEATURES_ENABLED=false` en el entorno (o el `GlobalPolicy`/`TenantPolicy` correspondiente).
2. Los endpoints IA responden 503 "IA deshabilitada"; la gestión de tickets sigue intacta.
3. Confirmar en el dashboard que `ai_disabled_total` sube (esperado) y que no hay 5xx en tickets.
4. Investigar en el runbook de incidentes; re-habilitar solo tras verificación.

## Procedimiento de rollback de versión

1. Identificar el último tag estable:

   ```bash
   git tag --list 'v*' | sort -V | tail -3
   ```

2. Redeployar ese tag (pipeline de release manual con el tag anterior).

3. Verificar `/health` devuelve la `version` anterior y el smoke CI del tag pasa.

4. Registrar el incidente y el rollback en `ia_docs/cambios.md` y `audit_events` (`ops.rollback`).

5. Post-mortem: root cause, tests de regresión y hotfix en `develop` (no en `main` sin aprobación).

## Reglas

- No hacer rollback de un release por un solo alerta: confirmar con métricas y auditoría antes.
- Un rollback no borra el tag; se deja la historia y se documenta por qué.
- Nunca rollbackear directo a `main`: volver al último tag estable.
