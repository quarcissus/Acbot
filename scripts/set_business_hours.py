"""
Configura los horarios de atención de un tenant.

Uso interactivo:
    python scripts/set_business_hours.py --tenant-slug acvex

Uso con argumentos (para automatizar):
    python scripts/set_business_hours.py --tenant-slug acvex --preset barberia
    python scripts/set_business_hours.py --tenant-slug acvex --preset lunes-sabado

Presets disponibles:
    barberia    → L-V 8-20, Sáb 8-18, Dom cerrado (default)
    lunes-viernes → L-V 8-20, Sáb cerrado, Dom cerrado
    lunes-sabado  → L-Sáb 8-20, Dom cerrado
    todos-los-dias → L-Dom 9-18
"""

import asyncio
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.core.database import AsyncSessionLocal, engine, Base
from app.models.tenant import Tenant
from app.models.business_hours import BusinessHours, WEEKDAY_NAMES

PRESETS = {
    "barberia": [
        {"weekday": 0, "is_open": True,  "open_time": "08:00", "close_time": "20:00"},
        {"weekday": 1, "is_open": True,  "open_time": "08:00", "close_time": "20:00"},
        {"weekday": 2, "is_open": True,  "open_time": "08:00", "close_time": "20:00"},
        {"weekday": 3, "is_open": True,  "open_time": "08:00", "close_time": "20:00"},
        {"weekday": 4, "is_open": True,  "open_time": "08:00", "close_time": "20:00"},
        {"weekday": 5, "is_open": True,  "open_time": "08:00", "close_time": "18:00"},
        {"weekday": 6, "is_open": False, "open_time": "10:00", "close_time": "15:00"},
    ],
    "lunes-viernes": [
        {"weekday": 0, "is_open": True,  "open_time": "08:00", "close_time": "20:00"},
        {"weekday": 1, "is_open": True,  "open_time": "08:00", "close_time": "20:00"},
        {"weekday": 2, "is_open": True,  "open_time": "08:00", "close_time": "20:00"},
        {"weekday": 3, "is_open": True,  "open_time": "08:00", "close_time": "20:00"},
        {"weekday": 4, "is_open": True,  "open_time": "08:00", "close_time": "20:00"},
        {"weekday": 5, "is_open": False, "open_time": "09:00", "close_time": "14:00"},
        {"weekday": 6, "is_open": False, "open_time": "09:00", "close_time": "14:00"},
    ],
    "lunes-sabado": [
        {"weekday": 0, "is_open": True,  "open_time": "08:00", "close_time": "20:00"},
        {"weekday": 1, "is_open": True,  "open_time": "08:00", "close_time": "20:00"},
        {"weekday": 2, "is_open": True,  "open_time": "08:00", "close_time": "20:00"},
        {"weekday": 3, "is_open": True,  "open_time": "08:00", "close_time": "20:00"},
        {"weekday": 4, "is_open": True,  "open_time": "08:00", "close_time": "20:00"},
        {"weekday": 5, "is_open": True,  "open_time": "08:00", "close_time": "20:00"},
        {"weekday": 6, "is_open": False, "open_time": "09:00", "close_time": "14:00"},
    ],
    "todos-los-dias": [
        {"weekday": i, "is_open": True, "open_time": "09:00", "close_time": "18:00"}
        for i in range(7)
    ],
}


async def set_hours(tenant_slug: str, hours_data: list[dict]) -> None:
    # Crear tabla si no existe
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        # Buscar tenant
        result = await db.execute(select(Tenant).where(Tenant.slug == tenant_slug))
        tenant = result.scalar_one_or_none()
        if not tenant:
            print(f"❌ Tenant '{tenant_slug}' no encontrado")
            sys.exit(1)

        # Borrar horarios existentes
        existing = await db.execute(
            select(BusinessHours).where(BusinessHours.tenant_id == tenant.id)
        )
        for bh in existing.scalars().all():
            await db.delete(bh)

        # Crear nuevos
        for h in hours_data:
            bh = BusinessHours(
                tenant_id=tenant.id,
                weekday=h["weekday"],
                is_open=h["is_open"],
                open_time=h["open_time"],
                close_time=h["close_time"],
            )
            db.add(bh)

        await db.commit()

        print(f"\n✅ Horarios configurados para: {tenant.name}")
        print()
        for h in sorted(hours_data, key=lambda x: x["weekday"]):
            name = WEEKDAY_NAMES[h["weekday"]]
            if h["is_open"]:
                print(f"  {name}: {h['open_time']} - {h['close_time']}")
            else:
                print(f"  {name}: cerrado")


async def interactive_mode(tenant_slug: str) -> None:
    """Modo interactivo para configurar horarios día por día."""
    print(f"\nConfigurando horarios para tenant: {tenant_slug}")
    print("Para cada día ingresa el horario o 'cerrado'\n")

    hours_data = []
    for weekday, name in WEEKDAY_NAMES.items():
        while True:
            entry = input(f"{name} (ej: 08:00-20:00 o cerrado): ").strip().lower()
            if entry == "cerrado" or entry == "":
                hours_data.append({
                    "weekday": weekday, "is_open": False,
                    "open_time": "09:00", "close_time": "18:00"
                })
                break
            elif "-" in entry:
                parts = entry.split("-")
                if len(parts) == 2:
                    hours_data.append({
                        "weekday": weekday, "is_open": True,
                        "open_time": parts[0].strip(),
                        "close_time": parts[1].strip()
                    })
                    break
            print("  Formato inválido. Usa HH:MM-HH:MM o 'cerrado'")

    await set_hours(tenant_slug, hours_data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Configurar horarios de un tenant")
    parser.add_argument("--tenant-slug", required=True)
    parser.add_argument("--preset", choices=list(PRESETS.keys()),
                        help="Usar un preset de horarios predefinido")
    args = parser.parse_args()

    if args.preset:
        asyncio.run(set_hours(args.tenant_slug, PRESETS[args.preset]))
    else:
        asyncio.run(interactive_mode(args.tenant_slug))