"""
Factory de handlers — retorna el handler correcto según el business_type del tenant.
"""

from app.handlers.base import BaseHandler
from app.handlers.barberia import BarberiaHandler
from app.handlers.doctor import DoctorHandler
from app.handlers.academia import AcademiaHandler

_handlers: dict[str, BaseHandler] = {
    "barberia": BarberiaHandler(),
    "doctor": DoctorHandler(),
    "academia": AcademiaHandler(),
}


def get_handler(business_type: str) -> BaseHandler:
    """
    Retorna el handler correspondiente al tipo de negocio.
    Si no existe, usa el de barbería como fallback.
    """
    return _handlers.get(business_type, BarberiaHandler())
