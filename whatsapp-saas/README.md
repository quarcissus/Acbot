# WhatsApp SaaS — Setup Fase 1

## Requisitos
- Python 3.12+
- PostgreSQL corriendo localmente (o Supabase)
- Cuenta de Meta Cloud API configurada

## Setup inicial

```bash
# 1. Clonar y entrar al proyecto
cd whatsapp-saas

# 2. Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env
# Editar .env con tus credenciales reales

# 5. Crear base de datos
createdb whatsapp_saas  # o crear desde psql

# 6. Correr migraciones
alembic upgrade head

# 7. Crear primer tenant
python scripts/create_tenant.py \
  --name "Barbería Don Pepe" \
  --type barberia \
  --phone "+5213312345678" \
  --phone-id "TU_PHONE_ID" \
  --waba-id "TU_WABA_ID"

# 8. Iniciar servidor
uvicorn app.main:app --reload --port 8000

# 9. Exponer al internet (para que Meta pueda enviar webhooks)
ngrok http 8000
# Copiar la URL https://xxx.ngrok.io y configurarla en Meta como webhook URL
```

## Correr tests
```bash
pytest tests/ -v
```

## Verificar que funciona
1. Ve a https://tu-ngrok-url.ngrok.io/docs
2. Configura el webhook en Meta: URL = https://tu-ngrok-url/webhook
3. Envía un mensaje al número de WhatsApp del tenant
4. Debes recibir "Echo [Barbería Don Pepe]: tu mensaje"
