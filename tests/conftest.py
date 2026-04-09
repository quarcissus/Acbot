"""
Configuración global de pytest.
"""

import pytest


# Necesario para que pytest-asyncio funcione con async tests
pytest_plugins = ("pytest_asyncio",)
