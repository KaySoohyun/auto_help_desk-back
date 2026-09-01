#!/usr/bin/env python3
"""Seed de usuarios y tickets demo para presentación.

Crea usuarios demo con credenciales conocidas (una por rol) y tickets de
ejemplo por tenant, de modo que los botones de acceso rápido del frontend
(feature 014) funcionen al instante y las bandejas tengan contenido.

Credenciales demo (públicas por diseño; producto de presentación):
    demo.agente@example.com      / demo-pass-123   (agent)
    demo.supervisor@example.com  / demo-pass-123   (supervisor)
    demo.admin@example.com       / demo-pass-123   (tenant_admin)
    demo.plataforma@example.com  / demo-pass-123   (platform_admin, sin tenant)
    demo.cliente.<slug>@example.com / demo-pass-123 (customer, una por tenant)

Idempotente: se puede correr varias veces sin duplicar usuarios, membresías,
customers ni tickets.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, select

from app.core.config import settings
from app.core.crypto import decrypt_field
from app.core.security import hash_password
from app.database import SessionLocal
from app.models.customer import Customer
from app.models.tenant import Tenant
from app.models.ticket import Ticket
from app.models.user import User
from app.repositories.tickets import TicketRepository
from app.repositories.user_tenant import UserTenantRepository

DEMO_PASSWORD = "demo-pass-123"
DEMO_SUBJECT_PREFIX = "[Demo]"

SUPPORT_DEMO_USERS = [
    {"email": "demo.agente@example.com", "role": "agent", "name": "Agente Demo"},
    {"email": "demo.supervisor@example.com", "role": "supervisor", "name": "Supervisor Demo"},
    {"email": "demo.admin@example.com", "role": "tenant_admin", "name": "Admin Empresa Demo"},
]

PLATFORM_DEMO_USER = {"email": "demo.plataforma@example.com", "role": "platform_admin", "name": "Admin Plataforma Demo"}

# Plantilla de tickets por tenant. `status` se aplica después del create.
TICKET_TEMPLATES = [
    {
        "subject": "[Demo] No puedo acceder a mi cuenta",
        "description": "Desde ayer me pide credenciales de nuevo y con las que tengo no entra. Necesito recuperar el acceso urgente.",
        "category": "technical",
        "priority": "high",
        "status": "open",
        "customer": True,
        "assigned": True,
        "messages": [
            ("customer", "Hola, no puedo ingresar a mi cuenta desde ayer. Me dice que las credenciales son inválidas."),
            ("agent", "Hola, gracias por el detalle. ¿Podés confirmar si probaste con la opción 'Olvidé mi contraseña'? Mientras tanto reviso el usuario."),
        ],
    },
    {
        "subject": "[Demo] Duda sobre la factura del mes",
        "description": "Me llegó la factura con un monto mayor al plan contratado. Quisiera saber a qué corresponde el adicional.",
        "category": "billing",
        "priority": "medium",
        "status": "on_hold",
        "customer": True,
        "assigned": False,
        "messages": [
            ("customer", "Adjunto la factura. El total no coincide con lo que contraté."),
            ("agent", "Estamos revisando el detalle de cargos. Te respondemos en el transcurso del día."),
        ],
    },
    {
        "subject": "[Demo] El sistema no envía notificaciones",
        "description": "No recibo los correos de alerta ni las notificaciones push de la app desde la última actualización.",
        "category": "technical",
        "priority": "medium",
        "status": "on_hold",
        "customer": False,
        "assigned": True,
        "messages": [],
    },
    {
        "subject": "[Demo] Solicitud de reembolso",
        "description": "Quiero solicitar el reembolso del último mes porque el servicio no funcionó durante varios días.",
        "category": "billing",
        "priority": "high",
        "status": "open",
        "customer": True,
        "assigned": True,
        "messages": [
            ("customer", "Necesito el reembolso del mes de julio por el corte de servicio."),
        ],
    },
    {
        "subject": "[Demo] Consulta general sobre el plan",
        "description": "Quiero saber si el plan actual permite agregar más usuarios y qué costo tendría el upgrade.",
        "category": "general",
        "priority": "low",
        "status": "closed",
        "customer": True,
        "assigned": False,
        "messages": [
            ("customer", "¿El plan enterprise incluye más de 10 usuarios?"),
            ("agent", "Sí, el plan enterprise no tiene límite de usuarios. Te dejo el detalle de precios."),
        ],
    },
]


def _get_or_create_user(db, email: str, role: str, tenant_id: str | None, name: str = "") -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is not None:
        if name and user.name != name:
            user.name = name
            db.commit()
        return user
    user = User(
        email=email,
        name=name or None,
        password_hash=hash_password(DEMO_PASSWORD),
        role=role,
        tenant_id=tenant_id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    print(f"  Usuario demo creado: {email} (id={user.id}, role={role})")
    return user


def _ensure_membership(db, user_id: int, tenant_id: str, role: str) -> None:
    repo = UserTenantRepository(db)
    if not repo.user_has_tenant(user_id, tenant_id):
        repo.create(user_id, tenant_id, role)
        print(f"  Membresía creada: {user_id} -> {tenant_id} ({role})")


def _get_or_create_demo_customer(db, tenant) -> Customer:
    """Cliente demo por tenant: user + membresía + fila en customers (como el registro)."""
    email = f"demo.cliente.{tenant.slug}@example.com"
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = _get_or_create_user(
            db, email, "customer", tenant.id, name=f"Cliente Demo · {tenant.name}"
        )
    else:
        _ensure_name(db, user, f"Cliente Demo · {tenant.name}")

    customer = db.scalar(
        select(Customer).where(Customer.email == email, Customer.tenant_id == tenant.id)
    )
    if customer is None:
        customer = Customer(
            tenant_id=tenant.id,
            name=f"Cliente Demo · {tenant.name}",
            email=email,
            company=tenant.name,
            user_id=user.id,
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)
        print(f"  Cliente demo creado: {email} (customer_id={customer.id})")

    _ensure_membership(db, user.id, tenant.id, "customer")
    return customer


def _tenant_has_demo_tickets(db, tenant_id: str) -> bool:
    """True si el tenant ya tiene algún ticket demo (por asunto descifrado)."""
    rows = db.scalars(select(Ticket.subject).where(Ticket.tenant_id == tenant_id)).all()
    for encrypted in rows:
        try:
            subject = decrypt_field(encrypted, settings.encryption_key)
        except Exception:
            continue
        if subject.startswith(DEMO_SUBJECT_PREFIX):
            return True
    return False


def _seed_tenant_tickets(db, tenant, agent: User, customer: Customer) -> None:
    if _tenant_has_demo_tickets(db, tenant.id):
        print(f"  Tickets demo ya existen en {tenant.id}; se omiten.")
        return

    repo = TicketRepository(db, tenant_id=tenant.id)
    for template in TICKET_TEMPLATES:
        ticket = repo.create(
            subject=template["subject"],
            description=template["description"],
            category=template["category"],
            priority=template["priority"],
            assignee_id=agent.id if template["assigned"] else None,
            customer_id=customer.id if template["customer"] else None,
        )
        # Aplicar estado no-por-defecto y fecha escalonada sobre el ORM.
        orm_ticket = db.get(Ticket, ticket.id)
        orm_ticket.status = template["status"]
        db.commit()
        print(f"  Ticket demo creado: #{ticket.id} [{template['status']}] {template['subject']}")

        for author_kind, body in template["messages"]:
            author_id = customer.user_id if author_kind == "customer" else agent.id
            repo.add_message(ticket.id, author_id, body)


def _ensure_name(db, user: User, name: str) -> None:
    """Normaliza el nombre de un usuario demo existente."""
    if user is not None and name and user.name != name:
        user.name = name
        db.commit()
        print(f"  Nombre demo normalizado: {user.email} -> {name}")


def seed_support_users(db) -> dict[str, User]:
    """Usuarios de soporte compartidos con membresía en todos los tenants."""
    tenants = db.scalars(select(Tenant).order_by(Tenant.name)).all()
    users: dict[str, User] = {}

    for spec in SUPPORT_DEMO_USERS:
        user = db.scalar(select(User).where(User.email == spec["email"]))
        if user is None:
            user = _get_or_create_user(
                db, spec["email"], spec["role"], tenants[0].id if tenants else None, spec["name"]
            )
        else:
            _ensure_name(db, user, spec["name"])
        users[spec["email"]] = user
        for tenant in tenants:
            _ensure_membership(db, user.id, tenant.id, spec["role"])

    return users


def seed_platform_demo(db) -> None:
    user = db.scalar(select(User).where(User.email == PLATFORM_DEMO_USER["email"]))
    if user is None:
        _get_or_create_user(
            db,
            PLATFORM_DEMO_USER["email"],
            PLATFORM_DEMO_USER["role"],
            None,
            PLATFORM_DEMO_USER["name"],
        )
    else:
        _ensure_name(db, user, PLATFORM_DEMO_USER["name"])


def seed_per_tenant(db, users: dict[str, User]) -> None:
    tenants = db.scalars(select(Tenant).order_by(Tenant.name)).all()
    for tenant in tenants:
        print(f"\nTenant: {tenant.name} ({tenant.slug})")
        customer = _get_or_create_demo_customer(db, tenant)
        agent = users["demo.agente@example.com"]
        _seed_tenant_tickets(db, tenant, agent, customer)


def main() -> None:
    db = SessionLocal()
    try:
        print("Seeding usuarios demo de soporte...")
        support_users = seed_support_users(db)
        seed_platform_demo(db)
        seed_per_tenant(db, support_users)
        print("\n✓ Seed de demo completado.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
