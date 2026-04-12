"""
API REST — registra todos los routers del panel de control.
"""

from fastapi import FastAPI
from app.api import auth, tenants, appointments, staff, bot, stats, business_hours
from app.api.public import public_router


def register_api_routers(app: FastAPI) -> None:
    """Registra todos los routers de la API en la app FastAPI."""
    app.include_router(auth.router)
    app.include_router(tenants.router)
    app.include_router(appointments.router)
    app.include_router(public_router)
    app.include_router(staff.router)
    app.include_router(bot.router)
    app.include_router(stats.router)
    app.include_router(business_hours.router)