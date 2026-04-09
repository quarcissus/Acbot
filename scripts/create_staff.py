"""
Script CLI para agregar barberos/empleados a un tenant.

Uso:
    python scripts/create_staff.py \
        --tenant-slug "acvex" \
        --name "Carlos" \
        --role "barbero" \
        --duration 30
"""

import asyncio
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import AsyncSessionLocal
from app.services.tenant_service import get_tenant_by_slug, TenantNotFoundError
from app.services.staff_service import create_staff, get_active_staff


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Agregar empleado a un tenant")
    parser.add_argument("--tenant-slug", required=True, help="Slug del tenant (ej: acvex)")
    parser.add_argument("--name", required=True, help="Nombre del empleado")
    parser.add_argument("--role", default="barbero", help="Rol (default: barbero)")
    parser.add_argument("--duration", type=int, default=30, help="Minutos por cita (default: 30)")
    parser.add_argument("--yes", action="store_true", help="Saltar confirmación")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()

    async with AsyncSessionLocal() as db:
        # Verificar que el tenant existe
        try:
            tenant = await get_tenant_by_slug(db, args.tenant_slug)
        except TenantNotFoundError:
            print(f"✗ Tenant '{args.tenant_slug}' no encontrado")
            sys.exit(1)

        # Mostrar staff actual
        current_staff = await get_active_staff(db, tenant.id)
        print(f"\nTenant: {tenant.name}")
        if current_staff:
            print(f"Barberos actuales: {', '.join(s.name for s in current_staff)}")
        else:
            print("Sin barberos aún")

        print(f"\nAgregar:")
        print(f"  Nombre:   {args.name}")
        print(f"  Rol:      {args.role}")
        print(f"  Duración: {args.duration} min por cita")

        if not args.yes:
            confirm = input("\n¿Confirmar? [s/N]: ").strip().lower()
            if confirm not in ("s", "si", "sí", "y", "yes"):
                print("Cancelado.")
                sys.exit(0)

        staff = await create_staff(
            db=db,
            tenant_id=tenant.id,
            name=args.name,
            role=args.role,
            appointment_duration=args.duration,
        )

        print(f"\n✅ Empleado creado!")
        print(f"   ID:     {staff.id}")
        print(f"   Nombre: {staff.name}")

        # Mostrar staff actualizado
        all_staff = await get_active_staff(db, tenant.id)
        print(f"\nBarberos de {tenant.name}: {', '.join(s.name for s in all_staff)}")


if __name__ == "__main__":
    asyncio.run(main())