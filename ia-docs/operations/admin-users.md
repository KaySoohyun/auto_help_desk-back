# Usuarios administradores

_Usuarios con privilegios de operación en el despliegue de FastAPI Cloud (`https://auto-help-desk.fastapicloud.dev`)._

> Las **credenciales** viven en el `.env` local (gitignored), no en este repo versionado:
> `ADMIN_EMAIL` y `ADMIN_PASSWORD`. Este doc explica qué puede hacer el admin y cómo usarlo.

## Admin de plataforma

| Campo | Valor |
| --- | --- |
| Rol | `platform_admin` |
| Email | `ADMIN_EMAIL` (`.env`) |
| Password | `ADMIN_PASSWORD` (`.env`) |
| tenant_id | `null` (plataforma) |

El admin no se crea por `/auth/register`: ese endpoint público **rechaza roles admin** (403).
El admin de plataforma se provisiona por seed en la DB (o vía `/v1/admin/users` con otro `platform_admin`).

### Qué puede hacer

- Acceso a `/v1/ai/info` (config del orquestador LLM, sin secretos) — permiso `VIEW_AUDIT`.
- Acceso a `/v1/metrics` (Prometheus) — permiso `VIEW_AUDIT`.
- Consola de auditoría (`/v1/audit`) y administración de usuarios/tenants (`/v1/admin`).
- Usar `/v1/ai/ping` como smoke test del LLM.

### Cómo obtener un token

```bash
source .env 2>/dev/null   # expone ADMIN_EMAIL y ADMIN_PASSWORD

curl -s -X POST https://auto-help-desk.fastapicloud.dev/auth/login \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}"
# → {"access_token":"...", "refresh_token":"..."}
```

Luego usar el token como `Authorization: Bearer <access_token>` (expira en 15 min; renovar con `/auth/refresh`).

## Smoke test del LLM

```bash
source .env 2>/dev/null
TOKEN=$(curl -s -X POST https://auto-help-desk.fastapicloud.dev/auth/login \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

curl -s https://auto-help-desk.fastapicloud.dev/v1/ai/info -H "Authorization: Bearer $TOKEN"
curl -s -X POST https://auto-help-desk.fastapicloud.dev/v1/ai/ping \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"ticket_id":1}'
```

Respuesta esperada de ping: `{"ok":true,"model":"gemini-3.6-flash","trace_id":"..."}`.

## Roles y registro

| Rol | ¿Auto-registro público? | Permisos destacados |
| --- | --- | --- |
| `platform_admin` | No (403) | Todo (incluye `VIEW_AUDIT`, `MANAGE_AI_POLICIES`). |
| `tenant_admin` | No (403) | `VIEW_AUDIT`, gestión de usuarios del tenant. |
| `supervisor` | Sí | `VIEW_AUDIT`, lectura de tickets, sugerencias IA. |
| `agent` | Sí | Tickets y sugerencias IA de su tenant. |

Detalle completo de permisos en `app/core/permissions.py`; la restricción del registro en
`PUBLIC_REGISTRATION_ROLES` (`app/api/routes_auth.py`).

## Notas

- El `SECRET_KEY` de producción, las keys de LLM, `DATABASE_URL` y las credenciales admin viven en
  la consola de FastAPI Cloud (env vars) o en el `.env` local; **no en el repo**.
