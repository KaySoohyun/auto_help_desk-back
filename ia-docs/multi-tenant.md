# Sistema Multi-Tenant - Documentación Técnica

## Resumen

El sistema ahora soporta multi-tenant real, permitiendo que un usuario pertenezca a múltiples tenants con roles diferentes en cada uno.

## Arquitectura

### Modelo de Datos

#### Tabla `user_tenants`
Relación many-to-many entre usuarios y tenants con rol específico por tenant.

```python
class UserTenant(Base):
    __tablename__ = "user_tenants"
    
    id: int (PK)
    user_id: int (FK -> users.id)
    tenant_id: str (FK -> tenants.id)
    role: str  # Rol específico para este tenant
    created_at: datetime
    
    # Índices únicos
    - (user_id, tenant_id) UNIQUE
    - tenant_id INDEX
```

#### Modelo `User`
Actualizado para incluir relación con `user_tenants`:

```python
class User(Base):
    # ... campos existentes ...
    tenant_memberships: list[UserTenant]  # Relación con tenants
```

**Nota**: Se mantiene `users.tenant_id` por compatibilidad con código existente. Se eliminará en una futura migración.

### Autenticación Multi-Tenant

#### Flujo de Login

1. **Login sin tenant_id especificado**:
   - El usuario recibe tokens con su tenant principal (`users.tenant_id`)
   - Si no tiene tenant principal, recibe tokens sin tenant

2. **Login con tenant_id especificado**:
   - El sistema verifica que el usuario pertenezca a ese tenant
   - Los tokens incluyen el `tenant_id` y `role` específicos de ese tenant
   - Si el usuario no pertenece al tenant, se rechaza con 403

#### Cambio de Tenant

Después del login, el usuario puede cambiar de tenant usando:

```http
POST /auth/switch-tenant
Content-Type: application/json
Authorization: Bearer <access_token>

{
  "tenant_id": "nuevo-tenant-id"
}
```

El sistema:
1. Verifica que el usuario pertenezca al tenant
2. Emite nuevos tokens con el `tenant_id` y `role` del nuevo tenant
3. Registra el cambio en auditoría

#### Listar Tenants del Usuario

```http
GET /auth/tenants
Authorization: Bearer <access_token>
```

Respuesta:
```json
[
  {
    "id": "tenant-1",
    "name": "Tenant 1",
    "slug": "tenant-1",
    "role": "agent"
  },
  {
    "id": "tenant-2",
    "name": "Tenant 2",
    "slug": "tenant-2",
    "role": "supervisor"
  }
]
```

### Tokens JWT

Los tokens ahora incluyen:
- `sub`: ID del usuario
- `tenant_id`: ID del tenant activo
- `roles`: Lista con el rol del usuario en el tenant activo
- `type`: "access" o "refresh"

**Ejemplo de payload**:
```json
{
  "sub": "123",
  "tenant_id": "tenant-abc",
  "roles": ["agent"],
  "type": "access",
  "exp": 1234567890
}
```

### Respuesta de `/auth/me`

Ahora incluye la lista de tenants del usuario:

```json
{
  "id": 123,
  "email": "user@example.com",
  "role": "agent",
  "tenant_id": "tenant-abc",
  "is_active": true,
  "created_at": "2026-01-01T00:00:00Z",
  "tenants": [
    {
      "id": "tenant-abc",
      "name": "Tenant ABC",
      "slug": "tenant-abc",
      "role": "agent"
    },
    {
      "id": "tenant-xyz",
      "name": "Tenant XYZ",
      "slug": "tenant-xyz",
      "role": "supervisor"
    }
  ]
}
```

## Migración de Datos

### Script de Migración

El script `scripts/migrate_user_tenants.py` realiza:

1. Crea la tabla `user_tenants` si no existe
2. Crea tenants faltantes en la tabla `tenants` (para usuarios con `tenant_id` que no existe en `tenants`)
3. Migra todos los usuarios con `tenant_id` a `user_tenants`
4. Verifica que todos los usuarios fueron migrados correctamente

**Ejecución**:
```bash
cd /home/kona/backend-python
source .venv/bin/activate
python scripts/migrate_user_tenants.py
```

**Resultado esperado**:
```
Iniciando migración de users.tenant_id a user_tenants...
Tabla user_tenants verificada/creada.
Verificando tenants faltantes...
Tenants faltantes creados.
Encontrados 190 usuarios con tenant_id para migrar.
Migración completada. 190 registros en user_tenants.
Todos los usuarios fueron migrados correctamente.
Migración completada.
```

## Compatibilidad

### Código Legacy

El sistema mantiene compatibilidad con código que usa `users.tenant_id`:

- `User.tenant_id` sigue existiendo y se usa como tenant principal
- Los endpoints que no especifican `tenant_id` usan `users.tenant_id`
- Los tokens JWT incluyen `tenant_id` del tenant activo

### Próximos Pasos

1. **Actualizar código legacy**: Migrar todo el código que usa `users.tenant_id` a usar `user_tenants`
2. **Eliminar columna `users.tenant_id`**: Después de migrar todo el código
3. **Eliminar columna `kb_articles.tags`**: Después de verificar que todo el código usa `article_tags`

## Seguridad

### Aislamiento de Tenants

- Cada token JWT incluye el `tenant_id` activo
- Los endpoints verifican que el usuario pertenezca al tenant del token
- Los datos siempre se filtran por `tenant_id`
- No hay fuga de datos entre tenants

### Permisos por Tenant

- Un usuario puede tener roles diferentes en diferentes tenants
- Los permisos se verifican contra el rol del usuario en el tenant activo
- El cambio de tenant requiere emitir nuevos tokens con el rol correcto

## Testing

### Tests de Multi-Tenant

Los tests verifican:
- Login con y sin `tenant_id`
- Cambio de tenant con `switch-tenant`
- Listado de tenants del usuario
- Aislamiento de datos entre tenants
- Permisos específicos por tenant

**Ejecutar tests**:
```bash
cd /home/kona/backend-python
source .venv/bin/activate
pytest tests/ -v
```

**Resultado esperado**: 276 tests pasan

## Frontend

### Cambios Necesarios en Frontend

El frontend necesita actualizar:

1. **Login**: Permitir seleccionar tenant si el usuario tiene múltiples tenants
2. **Tenant Switcher**: Usar `/auth/switch-tenant` para cambiar de tenant
3. **User Menu**: Mostrar lista de tenants del usuario
4. **Tokens**: Manejar tokens con `tenant_id` específico

### Endpoints a Consumir

- `POST /auth/login` con `tenant_id` opcional
- `POST /auth/switch-tenant` para cambiar de tenant
- `GET /auth/tenants` para listar tenants
- `GET /auth/me` para obtener información del usuario con tenants

## Referencias

- **Modelo**: `app/models/user_tenant.py`
- **Schema**: `app/schemas/user_tenant.py`, `app/schemas/auth.py`
- **Repositorio**: `app/repositories/user_tenant.py`
- **Endpoints**: `app/api/routes_auth.py`
- **Migración**: `scripts/migrate_user_tenants.py`
- **Tests**: `tests/test_auth.py`, `tests/test_multi_tenant.py` (si existe)
