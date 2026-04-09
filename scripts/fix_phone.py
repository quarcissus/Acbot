import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import AsyncSessionLocal
from app.models.tenant import Tenant
from sqlalchemy import update

async def fix():
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(Tenant)
            .where(Tenant.slug == "acvex")
            .values(phone_number="+524492762190")
        )
        await db.commit()
        print("✅ Número actualizado a +524492762190")

asyncio.run(fix())