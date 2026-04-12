"""
Punto de entrada de la aplicación FastAPI.
Registra routers, configura logging y eventos de startup/shutdown.
"""

import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import settings
from app.core.database import engine, Base
from app.gateway.webhook import router as webhook_router
from app.api import register_api_routers
from app.services.reminder_service import start_scheduler, stop_scheduler
import app.models  # noqa: F401 — necesario para que Base conozca los modelos

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if not settings.is_production else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


# ── Lifespan (startup / shutdown) ────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Acciones al iniciar y apagar la aplicación."""
    logger.info(f"🚀 WhatsApp SaaS iniciando — entorno: {settings.environment}")
    logger.info(f"   DB: {settings.database_url.split('@')[-1]}")
    logger.info(f"   Meta API version: {settings.meta_api_version}")

    # Crear tablas si no existen
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ tables verified/created")

    # Iniciar scheduler de recordatorios
    start_scheduler()

    yield  # La app corre aquí

    # Apagado limpio
    stop_scheduler()
    logger.info("Apagando aplicación...")
    await engine.dispose()
    logger.info("Conexiones de DB cerradas")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="WhatsApp SaaS",
    description="Plataforma multi-tenant de chatbot con WhatsApp",
    version="0.3.0",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url=None,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=(
        ["*"] if not settings.is_production
        else [
            settings.webhook_base_url,
            "http://localhost:5173",
            "http://localhost:3000",
            "https://acvex-panel.vercel.app",
            "https://somo-barbaros.vercel.app",
            "https://somo-barbaros-h0z641x8t-quarcissus-projects.vercel.app",
        ]
    ),
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(webhook_router)
register_api_routers(app)


@app.get("/", tags=["health"])
async def root() -> dict:
    return {"status": "ok", "service": "whatsapp-saas", "version": "0.3.0"}


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    return {
        "status": "healthy",
        "environment": settings.environment,
        "meta_configured": bool(settings.meta_access_token),
        "openai_configured": bool(settings.openai_api_key),
        "scheduler_running": True,
    }