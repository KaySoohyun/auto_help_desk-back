from fastapi import FastAPI

from app import __version__
from app.api.routes_admin import router as admin_router
from app.api.routes_agents import router as agents_router
from app.api.routes_ai import router as ai_router
from app.api.routes_audit import router as audit_router
from app.api.routes_auth import router as auth_router
from app.api.routes_customers import router as customers_router
from app.api.routes_kb import router as kb_router
from app.api.routes_metrics import router as metrics_router
from app.api.routes_persona import router as persona_router
from app.api.routes_pii import router as pii_router
from app.api.routes_tags import router as tags_router
from app.api.routes_tenants import router as tenants_router
from app.api.routes_tickets import router as tickets_router
from app.api.routes_workspace import router as workspace_router
from app.core.config import settings
from app.core.error_handlers import register_error_handlers
from app.core.observability import MetricsMiddleware
from app.database import Base, engine

app = FastAPI(title=settings.app_name)

app.add_middleware(MetricsMiddleware)
register_error_handlers(app)

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(audit_router)
app.include_router(tickets_router)
app.include_router(pii_router)
app.include_router(metrics_router)
app.include_router(ai_router)
app.include_router(workspace_router)
app.include_router(kb_router)
app.include_router(tags_router)
app.include_router(agents_router)
app.include_router(customers_router)
app.include_router(persona_router)
app.include_router(tenants_router)


@app.on_event("startup")
def on_startup() -> None:
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health() -> dict[str, str]:
    """Health check del servicio. `version` alimenta el smoke de release (018)."""
    return {"status": "ok", "version": __version__}
