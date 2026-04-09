web: python -c "
import asyncio
from app.core.database import AsyncSessionLocal
from app.models.tenant import Tenant
from sqlalchemy import update

async def fix():
    async with AsyncSessionLocal() as db:
        await db.execute(update(Tenant).where(Tenant.slug=='acvex').values(phone_number='+524492762190'))
        await db.commit()
        print('Número actualizado')

asyncio.run(fix())
" && uvicorn app.main:app --host 0.0.0.0 --port $PORT