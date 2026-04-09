"""Limpia citas y cierra conversaciones activas."""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.database import AsyncSessionLocal
from sqlalchemy import text

async def main():
    async with AsyncSessionLocal() as db:
        r1 = await db.execute(text("DELETE FROM appointments"))
        r2 = await db.execute(text("UPDATE conversations SET status = 'closed'"))
        await db.commit()
        print(f"✅ {r1.rowcount} citas eliminadas")
        print(f"✅ {r2.rowcount} conversaciones cerradas")

asyncio.run(main())