"""
Migración one-time: agrega columna bot_enabled a la tabla contacts.
Correr UNA sola vez via Procfile trick en Railway.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import engine


async def migrate():
    async with engine.begin() as conn:
        await conn.execute(
            __import__("sqlalchemy").text(
                "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS bot_enabled BOOLEAN DEFAULT TRUE"
            )
        )
    print("✅ Columna bot_enabled agregada (o ya existía)")
    await engine.dispose()


asyncio.run(migrate())