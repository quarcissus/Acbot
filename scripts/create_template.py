"""
Script CLI para crear templates de WhatsApp en Meta Business Manager.
Los templates se aprueban en ~24h. Solo necesitas crearlos una vez.

Uso:
    python scripts/create_template.py \
        --waba-id "987654321" \
        --name "appointment_reminder" \
        --category UTILITY \
        --language es_MX \
        --body "Hola {{1}}, te recordamos tu cita de {{2}} el {{3}} en {{4}}."
"""

import asyncio
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from app.config.settings import settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crear un template de WhatsApp en Meta")
    parser.add_argument("--waba-id", required=True, help="WhatsApp Business Account ID")
    parser.add_argument("--name", required=True, help="Nombre del template (snake_case)")
    parser.add_argument(
        "--category",
        required=True,
        choices=["UTILITY", "MARKETING", "AUTHENTICATION"],
        help="Categoría del template",
    )
    parser.add_argument("--language", default="es_MX", help="Código de idioma (default: es_MX)")
    parser.add_argument("--body", required=True, help="Texto del template con {{1}}, {{2}}...")
    parser.add_argument("--header", help="Texto del header (opcional)")
    parser.add_argument("--footer", help="Texto del footer (opcional)")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()

    if not settings.meta_access_token:
        print("✗ META_ACCESS_TOKEN no configurado en .env")
        sys.exit(1)

    url = f"{settings.meta_graph_url}/{args.waba_id}/message_templates"
    headers = {
        "Authorization": f"Bearer {settings.meta_access_token}",
        "Content-Type": "application/json",
    }

    # Construir componentes del template
    components = [{"type": "BODY", "text": args.body}]
    if args.header:
        components.insert(0, {"type": "HEADER", "format": "TEXT", "text": args.header})
    if args.footer:
        components.append({"type": "FOOTER", "text": args.footer})

    payload = {
        "name": args.name,
        "category": args.category,
        "language": args.language,
        "components": components,
    }

    print(f"\nCreando template '{args.name}' en WABA {args.waba_id}...")
    print(f"Body: {args.body[:80]}{'...' if len(args.body) > 80 else ''}")

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(url, json=payload, headers=headers)

    if response.status_code in (200, 201):
        result = response.json()
        print(f"\n✅ Template creado!")
        print(f"   ID:     {result.get('id')}")
        print(f"   Status: {result.get('status', 'PENDING')}")
        print(f"   ⚠️  Los templates tardan ~24h en ser aprobados por Meta.")
    else:
        print(f"\n✗ Error de Meta: HTTP {response.status_code}")
        print(f"  {response.text}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
