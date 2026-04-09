# WhatsApp SaaS — Fase 1: Gateway Básico

## Setup rápido

### 1. Instalar dependencias
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configurar variables de entorno
```bash
cp .env.example .env
# Editar .env con tus valores reales
```

### 3. Crear base de datos y migraciones
```bash
# Crear la DB en PostgreSQL primero:
createdb whatsapp_saas

# Generar y aplicar migración inicial:
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

### 4. Correr la aplicación
```bash
uvicorn app.main:app --reload --port 8000
```

### 5. Crear tu primer tenant
```bash
python scripts/create_tenant.py \
  --name "Barbería Don Pepe" \
  --type barberia \
  --phone "+5213312345678" \
  --phone-id "TU_PHONE_NUMBER_ID" \
  --waba-id "TU_WABA_ID"
```

### 6. Exponer el webhook (desarrollo local)
```bash
# Instalar ngrok: https://ngrok.com
ngrok http 8000
# Copiar la URL https://xxxx.ngrok.io y configurarla en Meta Developer Console
# Webhook URL: https://xxxx.ngrok.io/webhook
# Verify token: el valor de META_VERIFY_TOKEN en tu .env
```

## Correr tests
```bash
pytest tests/ -v
```

## Endpoints disponibles en Fase 1
- `GET  /`          → health check básico
- `GET  /health`    → estado de la app y configuración
- `GET  /webhook`   → verificación de Meta
- `POST /webhook`   → mensajes entrantes de WhatsApp
- `GET  /docs`      → Swagger UI (solo en desarrollo)
