"""
API REST — registra todos los routers del panel de control.
"""

from fastapi import FastAPI
from app.api import auth, tenants, appointments, staff, bot, stats


def register_api_routers(app: FastAPI) -> None:
    """Registra todos los routers de la API en la app FastAPI."""
    app.include_router(auth.router)
    app.include_router(tenants.router)
    app.include_router(appointments.router)
    app.include_router(appointments.public_router)  # público, sin auth
    app.include_router(staff.router)
    app.include_router(staff.public_router)          # público, sin auth
    app.include_router(bot.router)
    app.include_router(stats.router)