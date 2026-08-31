# Runbook · Release

_Gatillar un release versionado (`vX.Y.Z`) a partir de `develop`._

## Requisitos

- Rama `develop` con la suite completa en verde (`pytest -q` → `N passed`).
- Job `release` del CI aprobado manualmente (gate de `environment: production`).
- `scripts/release.sh` y `.github/workflows/ci.yml` presentes (018).

## Procedimiento

1. Confirmar que `develop` está lista:

   ```bash
   git checkout develop && git pull && git status
   ```

2. Revisar que no queden pendientes en `roadmap.md` ni features sin mergear.

3. Verificar versión actual:

   ```bash
   rg "__version__" app/__init__.py
   ```

4. Si el cambio de versión mayor/menor es semántico, bumpear `__version__` en `app/__init__.py` y el smoke `/health` lo reflejará (`{"status": "ok", "version": "x.y.z"}`).

5. Ejecutar el script de release (valida suite + crea tag):

   ```bash
   ./scripts/release.sh --push
   ```

   Sin `--push`, crea el tag local sin publicar.

6. Confirmar que el tag se creó:

   ```bash
   git tag --list 'v*' | tail -5
   ```

7. Registrar en `ia_docs/cambios.md`: versión, fecha, ramas y descripción del release.

## Verificación post-release

- `curl -s <host>/health` → `version` coincide con el tag.
- Smoke CI en verde para el commit del tag.
- Dashboard: sin 5xx, `ai_disabled_total` = 0 (salvo que el kill-switch sea intencional).

## Rollback

Si el release falla en producción → runbook `rollback.md`.
