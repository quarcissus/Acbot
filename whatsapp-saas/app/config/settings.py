"""
Configuración central de la aplicación usando Pydantic Settings.
Lee variables de entorno desde .env automáticamente.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Meta Cloud API
    meta_app_id: str = ""
    meta_app_secret: str = ""
    meta_verify_token: str = "default_verify_token"
    meta_api_version: str = "v21.0"
    meta_access_token: str = ""

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/whatsapp_saas"

    # App
    app_secret_key: str = "cambia_esto_en_produccion"
    webhook_base_url: str = "http://localhost:8000"

    # Entorno
    environment: str = "development"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def meta_graph_url(self) -> str:
        return f"https://graph.facebook.com/{self.meta_api_version}"


@lru_cache()
def get_settings() -> Settings:
    """
    Retorna la instancia de settings cacheada.
    Usar con Depends(get_settings) en FastAPI o importar directamente.
    """
    return Settings()


# Instancia global para importar directamente donde no se use DI
settings = get_settings()
