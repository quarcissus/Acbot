"""
Crea el usuario administrador del panel de control.

Uso:
    python scripts/create_admin.py --email tu@email.com --password tupassword

Solo necesitas correrlo UNA vez. Guarda el email y password en un lugar seguro.
"""

import asyncio
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.admin_user import AdminUser
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def create_admin(email: str, password: str) -> None:
    async with AsyncSessionLocal() as db:
        # Verificar si ya existe
        result = await db.execute(select(AdminUser).where(AdminUser.email == email))
        existing = result.scalar_one_or_none()

        if existing:
            print(f"⚠️  Ya existe un admin con email: {email}")
            print("Si quieres cambiar la contraseña, elimina el registro manualmente.")
            return

        admin = AdminUser(
            email=email,
            hashed_password=pwd_context.hash(password),
        )
        db.add(admin)
        await db.commit()
        await db.refresh(admin)
        print(f"✅ Admin creado exitosamente")
        print(f"   Email: {admin.email}")
        print(f"   ID:    {admin.id}")
        print(f"\nAhora puedes hacer login en: POST /api/auth/login")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crear usuario admin del panel")
    parser.add_argument("--email", required=True, help="Email del admin")
    parser.add_argument("--password", required=True, help="Contraseña del admin")
    args = parser.parse_args()

    if len(args.password) < 8:
        print("❌ La contraseña debe tener al menos 8 caracteres")
        sys.exit(1)

    asyncio.run(create_admin(args.email, args.password))