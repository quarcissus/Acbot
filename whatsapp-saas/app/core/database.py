"""
Configuración de SQLAlchemy con soporte async.
Provee: engine, session factory, Base declarativo, y dependencia para FastAPI.
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase
from app.config.settings import settings


# Motor async — pool_pre_ping verifica conexiones muertas automáticamente
engine = create_async_engine(
    settings.database_url,
    echo=settings.environment == "development",  # Loguea SQL en dev
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

# Factory de sesiones async
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Evita lazy-load errors después de commit
)


class Base(DeclarativeBase):
    """Base declarativa para todos los modelos SQLAlchemy."""
    pass


async def get_db() -> AsyncSession:
    """
    Dependencia de FastAPI para inyectar sesión de base de datos.
    
    Uso:
        @router.get("/")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_all_tables() -> None:
    """
    Crea todas las tablas en la DB.
    Solo para desarrollo/testing. En producción usar Alembic.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_all_tables() -> None:
    """Elimina todas las tablas. Solo para testing."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
