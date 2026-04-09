"""
SecurityService — protección contra prompt injection y ataques comunes.
Filtra mensajes entrantes antes de pasarlos a la IA.
"""

import re
import logging

logger = logging.getLogger(__name__)

# ── Patrones de prompt injection ──────────────────────────────────────────────

INJECTION_PATTERNS = [
    # Intentos de ignorar instrucciones
    r"ignora\s+(todas?\s+)?(las?\s+)?(instrucciones|reglas|sistema|prompt)",
    r"olvida\s+(todo|las?\s+instrucciones|tu\s+rol)",
    r"ignore\s+(all\s+)?(previous\s+)?(instructions|rules|system)",
    r"forget\s+(everything|instructions|your\s+role)",
    r"disregard\s+(all\s+)?(previous\s+)?instructions",

    # Intentos de cambiar el rol
    r"ahora\s+(eres|serás|actúa\s+como)\s+",
    r"now\s+you\s+are\s+",
    r"pretend\s+(you\s+are|to\s+be)\s+",
    r"actúa\s+como\s+si\s+(no\s+tuvieras|fueras)",
    r"jailbreak",
    r"dan\s+mode",
    r"modo\s+dios",
    r"developer\s+mode",
    r"modo\s+desarrollador",

    # Intentos de extraer el system prompt
    r"muestra\s+(tu\s+)?(system\s+prompt|instrucciones\s+originales|prompt\s+completo)",
    r"repite\s+(tu\s+)?(system\s+prompt|instrucciones)",
    r"show\s+(me\s+)?(your\s+)?(system\s+prompt|instructions)",
    r"what\s+are\s+your\s+(system\s+)?instructions",
    r"cuáles\s+son\s+tus\s+instrucciones",

    # Inyección de rol de sistema
    r"\[system\]",
    r"\<system\>",
    r"###\s*system",
    r"###\s*instrucciones",

    # Intentos de acceso a datos
    r"lista\s+(todos?\s+)?(los?\s+)?(clientes|usuarios|números|teléfonos)",
    r"muestra\s+(la\s+)?(base\s+de\s+datos|todos\s+los\s+registros)",
    r"select\s+\*\s+from",
    r"drop\s+table",
]

# ── Límites de longitud ───────────────────────────────────────────────────────

MAX_MESSAGE_LENGTH = 1000   # caracteres máximos por mensaje
MAX_WORD_LENGTH = 50        # palabra más larga permitida (evita spam de caracteres)

# ── Respuestas de rechazo ─────────────────────────────────────────────────────

REJECTION_RESPONSES = [
    "Lo siento, no puedo ayudarte con eso. ¿Hay algo más en lo que pueda asistirte?",
    "Ese tipo de solicitud está fuera de lo que puedo hacer. ¿En qué más te ayudo?",
    "No puedo procesar esa solicitud. ¿Tienes alguna pregunta sobre nuestros servicios?",
]

import random

def get_rejection_response() -> str:
    return random.choice(REJECTION_RESPONSES)


# ── Funciones principales ─────────────────────────────────────────────────────

def sanitize_message(message: str) -> str:
    """
    Limpia el mensaje antes de procesarlo:
    - Trunca si es demasiado largo
    - Elimina caracteres de control
    - Normaliza espacios
    """
    # Eliminar caracteres de control (excepto saltos de línea)
    message = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", message)

    # Truncar si es muy largo
    if len(message) > MAX_MESSAGE_LENGTH:
        message = message[:MAX_MESSAGE_LENGTH] + "..."
        logger.warning(f"Mensaje truncado a {MAX_MESSAGE_LENGTH} caracteres")

    # Normalizar espacios múltiples
    message = re.sub(r" {3,}", "  ", message)

    return message.strip()


def is_injection_attempt(message: str) -> bool:
    """
    Detecta si el mensaje parece un intento de prompt injection.
    Retorna True si se detecta un patrón sospechoso.
    """
    message_lower = message.lower()

    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, message_lower, re.IGNORECASE):
            logger.warning(f"Prompt injection detectado. Patrón: {pattern[:40]}...")
            return True

    # Verificar palabras individuales muy largas (posible bypass con concatenación)
    words = message.split()
    for word in words:
        if len(word) > MAX_WORD_LENGTH and not word.startswith("http"):
            logger.warning(f"Palabra sospechosamente larga detectada: {len(word)} chars")
            return True

    return False


def validate_and_sanitize(message: str) -> tuple[bool, str]:
    """
    Punto de entrada principal. Valida y sanitiza un mensaje entrante.

    Returns:
        (es_valido, mensaje_procesado)
        - Si es_valido=False, mensaje_procesado contiene la respuesta de rechazo
        - Si es_valido=True, mensaje_procesado contiene el mensaje limpio
    """
    if not message or not message.strip():
        return False, "No recibí ningún mensaje. ¿En qué te puedo ayudar?"

    # Sanitizar primero
    clean_message = sanitize_message(message)

    # Detectar injection
    if is_injection_attempt(clean_message):
        return False, get_rejection_response()

    return True, clean_message