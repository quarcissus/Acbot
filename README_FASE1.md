# Fase 1 — Gateway básico: Guía de setup

## Qué hace esta fase

- Recibe mensajes de WhatsApp vía webhook de Meta
- Verifica la firma de seguridad HMAC-SHA256
- Identifica al tenant por su `phone_number_id`
- Crea/encuentra contactos y conversaciones en la DB
- Responde con **"[Nombre del negocio] Echo: {mensaje}"**
- Estructura lista para conectar la IA en Fase 2

---

## 1. Requisitos previos

- Python 3.12+
- PostgreSQL corriendo localmente (o cuenta en Supabase)
- Una app en [Meta for Developers](https://developers.facebook.com/)
- Un número de WhatsApp Business vinculado a tu app

---

## 2. Instalación

```bash
# Clonar/entrar al proyecto
cd whatsapp-saas

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt
```

---

## 3. Configuración

```bash
# Copiar el archivo de ejemplo
cp .env.example .env

# Editar con tus valores reales
nano .env  # o tu editor favorito
```

Variables críticas para Fase 1:
```env
META_VERIFY_TOKEN=cualquier_string_que_elijas   # Lo usas al configurar el webhook en Meta
META_APP_SECRET=tu_app_secret_de_meta           # En Meta > App > Configuración básica
META_ACCESS_TOKEN=tu_token_permanente           # En Meta > WhatsApp > Configuración de API
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/whatsapp_saas
```

---

## 4. Base de datos

### Opción A: PostgreSQL local

```bash
# Crear la base de datos
psql -U postgres -c "CREATE DATABASE whatsapp_saas;"
psql -U postgres -c "CREATE USER wsaas_user WITH PASSWORD 'tu_password';"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE whatsapp_saas TO wsaas_user;"
```

### Opción B: Supabase (free tier)

1. Crear proyecto en [supabase.com](https://supabase.com)
2. Ir a Settings > Database > Connection string
3. Copiar la URI y reemplazar en `.env`

### Correr migraciones

```bash
# Generar la primera migración (detecta todos los modelos)
alembic revision --autogenerate -m "initial schema"

# Aplicar la migración
alembic upgrade head
```

---

## 5. Registrar el webhook en Meta

Necesitas exponer tu localhost a internet. Opciones:

### Opción A: ngrok (recomendado para desarrollo)
```bash
# Instalar ngrok: https://ngrok.com
ngrok http 8000

# Copia la URL https que te da, ej: https://abc123.ngrok.io
```

### Opción B: cloudflared tunnel (gratis)
```bash
cloudflared tunnel --url http://localhost:8000
```

Luego en **Meta for Developers**:
1. Ve a tu app → WhatsApp → Configuración
2. Webhook URL: `https://tu-url.ngrok.io/webhook`
3. Verify Token: el valor de `META_VERIFY_TOKEN` en tu `.env`
4. Suscribirse a: `messages`
5. Click en "Verificar y guardar"

---

## 6. Correr la aplicación

```bash
# Desarrollo con hot-reload
uvicorn app.main:app --reload --port 8000

# Verificar que corre
curl http://localhost:8000/health
# → {"status": "ok", "version": "0.1.0", "env": "development"}
```

---

## 7. Crear tu primer tenant

```bash
python scripts/create_tenant.py \
  --name "Barbería Don Pepe" \
  --type barberia \
  --phone "+5213312345678" \
  --phone-id "EL_PHONE_NUMBER_ID_DE_META" \
  --waba-id "EL_WABA_ID_DE_META"
```

> **¿Dónde encuentro phone-id y waba-id?**
> En Meta for Developers → Tu app → WhatsApp → Configuración de API.
> El **Phone Number ID** y el **WhatsApp Business Account ID** aparecen ahí.

---

## 8. Probar

Envía un mensaje de WhatsApp al número del negocio que configuraste.
Deberías recibir de vuelta:

```
[Barbería Don Pepe] Echo: tu mensaje aquí
```

Revisa los logs de uvicorn para ver el flujo completo.

---

## 9. Correr tests

```bash
pip install pytest pytest-asyncio
pytest tests/ -v
```

---

## Estructura de archivos de Fase 1

```
app/
├── main.py                  ← FastAPI app + lifespan
├── config/settings.py       ← Variables de entorno
├── core/
│   ├── database.py          ← SQLAlchemy async
│   └── security.py          ← Verificación HMAC de Meta
├── models/                  ← ORM (Tenant, Contact, Conversation, Message, Appointment)
├── schemas/tenant.py        ← Pydantic schemas
└── gateway/
    ├── webhook.py            ← GET /webhook + POST /webhook
    ├── router.py             ← Enrutar mensajes al handler correcto
    ├── sender.py             ← Enviar mensajes de texto
    └── template_sender.py   ← Enviar templates (para Fase 3)
scripts/
└── create_tenant.py         ← CLI para agregar clientes
```

---

## Siguiente: Fase 2 — Chatbot con IA

En Fase 2 se implementa:
- `app/services/ai_service.py` — integración con OpenAI GPT-4o-mini
- `app/handlers/base.py` → lógica real (ya tiene la interfaz)
- `app/handlers/barberia.py` — primer vertical completo
- El router de Fase 1 conectará con los handlers reales
