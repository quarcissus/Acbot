"""
Reset del usuario admin — borra el existente y crea uno nuevo.
Usar cuando no recuerdas las credenciales.

Uso en Procfile:
web: python scripts/reset_admin.py --email admin@acvex.com --password NuevoPass123 && uvicorn app.main:app --host 0.0.0.0 --port $PORT
"""

import asyncio
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete
from app.core.database import AsyncSessionLocal, engine, Base
from app.models.admin_user import AdminUser
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def reset_admin(email: str, password: str) -> None:
    # Crear tabla si no existe
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        # Borrar TODOS los admins existentes
        await db.execute(delete(AdminUser))
        await db.commit()
        print("🗑️  Admins anteriores eliminados")

        # Crear el nuevo
        admin = AdminUser(
            email=email,
            hashed_password=pwd_context.hash(password),
        )
        db.add(admin)
        await db.commit()
        await db.refresh(admin)

        print(f"✅ Admin creado exitosamente")
        print(f"   Email:    {admin.email}")
        print(f"   Password: {password}")
        print(f"   ID:       {admin.id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()

    if len(args.password) < 8:
        print("❌ La contraseña debe tener al menos 8 caracteres")
        sys.exit(1)

    asyncio.run(reset_admin(args.email, args.password))