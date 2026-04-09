"""
SecurityService — protección contra prompt injection y ataques comunes.
Filtra mensajes entrantes antes de pasarlos a la IA.
"""

import re
import random
import logging

logger = logging.getLogger(__name__)

INJECTION_PATTERNS = [
    # Intentos de ignorar instrucciones
    r"ignora\s+(todas?\s+)?(las?\s+)?(instrucciones|reglas|sistema|prompt)",
    r"olvida\s+(todo|las?\s+instrucciones|tu\s+rol)",
    r"ignore\s+(all\s+)?(previous\s+)?(instructions|rules|system)",
    r"forget\s+(everything|instructions|your\s+role)",
    r"disregard\s+(all\s+)?previous\s+instructions",

    # Intentos de cambiar el rol
    r"ahora\s+(eres|seras|actua\s+como)\s+",
    r"now\s+you\s+are\s+",
    r"pretend\s+(you\s+are|to\s+be)\s+",
    r"actua\s+como\s+si\s+(no\s+tuvieras|fueras)",
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
    r"cuales\s+son\s+tus\s+instrucciones",
    r"dime\s+(tu\s+)?(system\s+prompt|instrucciones|prompt|configuracion)",
    r"comparte\s+(tu\s+)?(system\s+prompt|instrucciones|configuracion)",
    r"cual\s+es\s+tu\s+(system\s+prompt|prompt|instruccion|configuracion)",
    r"que\s+(instrucciones|prompt|reglas)\s+(tienes|te\s+dieron|sigues)",
    r"como\s+(estas|fuiste)\s+(programado|configurado|instruido)",
    r"cual\s+es\s+tu\s+rol\s+real",
    r"cual\s+es\s+tu\s+verdadera\s+(funcion|tarea|proposito)",
    r"revela\s+(tu\s+)?(prompt|instrucciones|sistema)",
    r"tell\s+me\s+(your\s+)?(prompt|instructions|system\s+prompt)",
    r"reveal\s+(your\s+)?(prompt|instructions|system)",
    r"print\s+(your\s+)?(system\s+prompt|instructions)",
    r"output\s+(your\s+)?(system\s+prompt|instructions)",
    r"repeat\s+(your\s+)?(system\s+prompt|instructions)",

    # Inyección de rol de sistema
    r"\[system\]",
    r"<system>",
    r"###\s*system",
    r"###\s*instrucciones",
    r"<\s*/?instruction",
    r"\[INST\]",
    r"<\s*human\s*>",
    r"<\s*assistant\s*>",

    # Intentos de acceso a datos
    r"lista\s+(todos?\s+)?(los?\s+)?(clientes|usuarios|numeros|telefonos)",
    r"muestra\s+(la\s+)?(base\s+de\s+datos|todos\s+los\s+registros)",
    r"select\s+\*\s+from",
    r"drop\s+table",
    r"delete\s+from",

    # Otros ataques comunes
    r"bypass\s+(security|seguridad|filtro|filter)",
    r"override\s+(security|instructions|system)",
    r"you\s+are\s+now\s+(free|unrestricted|without\s+limits)",
    r"ahora\s+eres\s+(libre|sin\s+restricciones|sin\s+limites)",
    r"activa\s+(modo|el\s+modo)\s+(sin\s+censura|sin\s+filtros|libre)",
    r"enable\s+(unrestricted|jailbreak|dev)\s+mode",
    r"sudo\s+",
    r"admin\s+(mode|comando|command)",
]

MAX_MESSAGE_LENGTH = 1000
MAX_WORD_LENGTH = 50

REJECTION_RESPONSES = [
    "Lo siento, no puedo ayudarte con eso. ¿Hay algo más en lo que pueda asistirte?",
    "Ese tipo de solicitud está fuera de lo que puedo hacer. ¿En qué más te ayudo?",
    "No puedo procesar esa solicitud. ¿Tienes alguna pregunta sobre nuestros servicios?",
]


def get_rejection_response() -> str:
    return random.choice(REJECTION_RESPONSES)


def sanitize_message(message: str) -> str:
    message = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", message)
    if len(message) > MAX_MESSAGE_LENGTH:
        message = message[:MAX_MESSAGE_LENGTH] + "..."
        logger.warning(f"Mensaje truncado a {MAX_MESSAGE_LENGTH} caracteres")
    message = re.sub(r" {3,}", "  ", message)
    return message.strip()


def is_injection_attempt(message: str) -> bool:
    # Normalizar acentos para comparación
    normalized = message.lower()
    replacements = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n"}
    for accented, plain in replacements.items():
        normalized = normalized.replace(accented, plain)

    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, normalized, re.IGNORECASE):
            logger.warning(f"Prompt injection detectado. Patron: {pattern[:40]}...")
            return True

    words = message.split()
    for word in words:
        if len(word) > MAX_WORD_LENGTH and not word.startswith("http"):
            logger.warning(f"Palabra sospechosamente larga: {len(word)} chars")
            return True

    return False


def validate_and_sanitize(message: str) -> tuple[bool, str]:
    if not message or not message.strip():
        return False, "No recibi ningun mensaje. En que te puedo ayudar?"

    clean_message = sanitize_message(message)

    if is_injection_attempt(clean_message):
        return False, get_rejection_response()

    return True, clean_message