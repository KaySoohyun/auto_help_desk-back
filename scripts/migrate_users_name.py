#!/usr/bin/env python3
"""Migración: agrega `users.name` (VARCHAR(255), nullable) y backfill desde el email.

`Base.metadata.create_all` no altera tablas existentes, por lo que este script
aplica el ALTER idempotente. Para los usuarios existentes sin nombre se deriva
uno del local-part del email (mismo criterio que `customers.name`).

Ejecutar:
    .venv/bin/python scripts/migrate_users_name.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.database import SessionLocal


def _name_from_email(email: str) -> str:
    """Nombre de display derivado del local-part del email (p. ej. juan.perez → Juan Perez)."""
    if not email:
        return ""
    local = email.split("@")[0]
    return local.replace(".", " ").replace("_", " ").replace("-", " ").strip().title() or ""


def migrate():
    """Agrega users.name si no existe (idempotente) y hace backfill."""
    db = SessionLocal()
    try:
        result = db.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'users' "
                "AND column_name = 'name'"
            )
        )
        if result.scalar() > 0:
            print("users.name ya existe. Verificando backfill...")
        else:
            print("Agregando users.name ...")
            db.execute(text("ALTER TABLE users ADD COLUMN name VARCHAR(255)"))
            db.commit()
            print("users.name agregado.")

        backfilled = db.execute(
            text(
                "UPDATE users SET name = "
                "CASE "
                "WHEN email IS NOT NULL THEN "
                "INITCAP(REPLACE(REPLACE(REPLACE(SPLIT_PART(email, '@', 1), '.', ' '), '_', ' '), '-', ' ')) "
                "ELSE 'Usuario' END "
                "WHERE name IS NULL OR BTRIM(name) = ''"
            )
        )
        db.commit()
        print(f"Backfill completado: {backfilled.rowcount} usuarios actualizados.")
    finally:
        db.close()


if __name__ == "__main__":
    migrate()