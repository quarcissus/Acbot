"""
Migración manual: agrega columna staff_id a la tabla appointments
y crea la tabla staff si no existe.
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import engine
from sqlalchemy import text


async def main():
    async with engine.begin() as conn:
        # Crear tabla staff si no existe
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS staff (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                name VARCHAR(100) NOT NULL,
                role VARCHAR(50) DEFAULT 'barbero',
                is_active BOOLEAN DEFAULT TRUE,
                appointment_duration INTEGER DEFAULT 30,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """))
        print("✅ Tabla staff verificada")

        # Agregar columna staff_id a appointments si no existe
        await conn.execute(text("""
            ALTER TABLE appointments
            ADD COLUMN IF NOT EXISTS staff_id UUID REFERENCES staff(id) ON DELETE SET NULL
        """))
        print("✅ Columna staff_id agregada a appointments")

    print("✅ Migración completada")


asyncio.run(main())