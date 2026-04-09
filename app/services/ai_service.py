"""
AIService — integración con OpenAI GPT-4o-mini.
Maneja el historial de conversación y genera respuestas.
"""

import logging
import json
import re
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config.settings import settings
from app.models.conversation import Message

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=settings.openai_api_key)

CONTEXT_MESSAGES = 10  # Últimos N mensajes que se envían como contexto


async def get_conversation_history(
    db: AsyncSession,
    conversation_id,
    limit: int = CONTEXT_MESSAGES,
) -> list[dict]:
    """
    Carga los últimos N mensajes de una conversación para usarlos como contexto.
    Retorna lista en formato OpenAI: [{"role": "user"/"assistant", "content": "..."}]
    """
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .where(Message.role.in_(["user", "assistant"]))
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    messages = list(reversed(result.scalars().all()))

    return [{"role": msg.role, "content": msg.content} for msg in messages]


async def generate_response(
    system_prompt: str,
    conversation_history: list[dict],
    user_message: str,
) -> str:
    """
    Llama a OpenAI con el system prompt, historial y mensaje actual.

    Returns:
        Respuesta del modelo como string.
    """
    messages = [
        {"role": "system", "content": system_prompt},
        *conversation_history,
        {"role": "user", "content": user_message},
    ]

    try:
        logger.info(f"Llamando OpenAI modelo={settings.openai_model} mensajes={len(messages)}")
        logger.debug(f"Messages payload: {messages}")
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            max_tokens=500,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"Error llamando a OpenAI: {e}")
        logger.error(f"Modelo usado: {settings.openai_model}")
        logger.error(f"Num mensajes: {len(messages)}")
        return "Disculpa, estoy teniendo problemas técnicos. ¿Puedes intentarlo de nuevo?"


def parse_action(response_text: str) -> tuple[str, dict | None]:
    """
    Detecta si la respuesta del bot incluye una acción estructurada.

    Formato esperado:
        Texto normal de respuesta...
        ###ACTION###
        {"action": "create_appointment", "service": "...", ...}
        ###END_ACTION###

    Returns:
        (texto_limpio, accion_dict) — accion_dict es None si no hay acción.
    """
    pattern = r"###ACTION###\s*(.*?)\s*###END_ACTION###"
    match = re.search(pattern, response_text, re.DOTALL)

    if not match:
        return response_text.strip(), None

    clean_text = response_text[:match.start()].strip()
    try:
        action = json.loads(match.group(1))
        return clean_text, action
    except json.JSONDecodeError:
        logger.warning(f"No se pudo parsear la acción JSON: {match.group(1)}")
        return clean_text, None