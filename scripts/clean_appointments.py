"""Limpia citas de prueba para empezar fresh."""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.database import AsyncSessionLocal
from sqlalchemy import text

async def main():
    async with AsyncSessionLocal() as db:
        result = await db.execute(text("DELETE FROM appointments WHERE source = 'chatbot'"))
        await db.commit()
        print(f"✅ {result.rowcount} citas de prueba eliminadas")

asyncio.run(main())