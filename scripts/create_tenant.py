"""
Script CLI para crear un nuevo tenant (cliente/negocio) en la base de datos.

Uso:
    python scripts/create_tenant.py \
        --name "Barbería Don Pepe" \
        --type barberia \
        --phone "+5213312345678" \
        --phone-id "123456789" \
        --waba-id "987654321" \
        [--prompt-file prompts/barberia_don_pepe.txt]
        [--welcome "¡Hola! Soy el asistente de Don Pepe"]
"""

import asyncio
import argparse
import sys
import os

# Agregar el root del proyecto al path para poder importar 'app'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import AsyncSessionLocal
from app.schemas.tenant import TenantCreate
from app.services.tenant_service import create_tenant, slugify, TenantAlreadyExistsError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crear un nuevo tenant")
    parser.add_argument("--name", required=True, help="Nombre del negocio")
    parser.add_argument(
        "--type",
        required=True,
        choices=["barberia", "doctor", "academia"],
        help="Tipo de negocio",
    )
    parser.add_argument(
        "--phone",
        required=True,
        help="Número de WhatsApp del negocio (ej: +5213312345678)",
    )
    parser.add_argument(
        "--phone-id",
        required=True,
        help="Phone Number ID de Meta Cloud API",
    )
    parser.add_argument(
        "--waba-id",
        required=True,
        help="WhatsApp Business Account ID",
    )
    parser.add_argument(
        "--slug",
        help="Slug personalizado (auto-generado si no se provee)",
    )
    parser.add_argument(
        "--timezone",
        default="America/Mexico_City",
        help="Zona horaria (default: America/Mexico_City)",
    )
    parser.add_argument(
        "--prompt-file",
        help="Path a archivo .txt con el system prompt del bot",
    )
    parser.add_argument(
        "--welcome",
        help="Mensaje de bienvenida del bot",
    )
    parser.add_argument(
        "--reminder-hours",
        type=int,
        default=24,
        help="Horas antes para enviar recordatorio de cita (default: 24)",
    )
    parser.add_argument("--yes", action="store_true", help="Saltar confirmación")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()

    # Leer system prompt desde archivo si se proporcionó
    system_prompt = None
    if args.prompt_file:
        try:
            with open(args.prompt_file, "r", encoding="utf-8") as f:
                system_prompt = f.read().strip()
            print(f"✓ System prompt cargado desde {args.prompt_file}")
        except FileNotFoundError:
            print(f"✗ Archivo no encontrado: {args.prompt_file}")
            sys.exit(1)

    # Generar slug si no se proporcionó
    slug = args.slug or slugify(args.name)

    # Confirmar antes de crear
    print(f"\n{'='*50}")
    print(f"  Crear nuevo tenant:")
    print(f"  Nombre:       {args.name}")
    print(f"  Slug:         {slug}")
    print(f"  Tipo:         {args.type}")
    print(f"  Teléfono:     {args.phone}")
    print(f"  Phone ID:     {args.phone_id}")
    print(f"  WABA ID:      {args.waba_id}")
    print(f"  Timezone:     {args.timezone}")
    print(f"  Bot prompt:   {'Sí' if system_prompt else 'No (se puede agregar después)'}")
    print(f"{'='*50}")

    if "--yes" not in sys.argv:
        confirm = input("\n¿Confirmar creación? [s/N]: ").strip().lower()
        if confirm not in ("s", "si", "sí", "y", "yes"):
            print("Cancelado.")
            sys.exit(0)
    # Crear tenant
    tenant_data = TenantCreate(
        name=args.name,
        slug=slug,
        business_type=args.type,
        phone_number=args.phone,
        whatsapp_phone_id=args.phone_id,
        whatsapp_waba_id=args.waba_id,
        timezone=args.timezone,
        bot_system_prompt=system_prompt,
        bot_welcome_message=args.welcome,
        reminder_hours_before=args.reminder_hours,
    )

    async with AsyncSessionLocal() as db:
        try:
            tenant = await create_tenant(db, tenant_data)
            print(f"\n✅ Tenant creado exitosamente!")
            print(f"   ID:   {tenant.id}")
            print(f"   Slug: {tenant.slug}")
        except TenantAlreadyExistsError as e:
            print(f"\n✗ Error: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"\n✗ Error inesperado: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())
