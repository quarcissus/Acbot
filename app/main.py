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
from app.core.database import engine
from app.gateway.webhook import router as webhook_router


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
    logger.info(f"   DB: {settings.database_url.split('@')[-1]}")  # Oculta credenciales
    logger.info(f"   Meta API version: {settings.meta_api_version}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ tables verified/created")
    yield  # La app corre aquí

    logger.info("Apagando aplicación...")
    await engine.dispose()
    logger.info("Conexiones de DB cerradas")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="WhatsApp SaaS",
    description="Plataforma multi-tenant de chatbot con WhatsApp",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url=None,
)

# CORS — en producción limitar a tu dominio
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if not settings.is_production else [settings.webhook_base_url],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(webhook_router)
# Fase 4: app.include_router(tenants_router, prefix="/api/v1")
# Fase 4: app.include_router(contacts_router, prefix="/api/v1")


@app.get("/", tags=["health"])
async def root() -> dict:
    return {"status": "ok", "service": "whatsapp-saas", "version": "0.1.0"}


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    return {
        "status": "healthy",
        "environment": settings.environment,
        "meta_configured": bool(settings.meta_access_token),
        "openai_configured": bool(settings.openai_api_key),
    }
