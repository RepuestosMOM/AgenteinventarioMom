import re
from backend.odoo_client import (
    search_products,
    search_oem,
    search_by_model,
    format_product,
)

# OEM real: debe contener al menos un dígito (ej. 96445053, AB1234X)
_OEM_PATTERN = re.compile(r'\b(?=[A-Z0-9]*\d)[A-Z0-9]{5,}\b', re.IGNORECASE)

# Modelos de vehículos comunes para detectar búsqueda por modelo
_VEHICLE_KEYWORDS = [
    'aveo', 'sail', 'spark', 'corsa', 'astra', 'cruze', 'tracker',
    'corolla', 'yaris', 'hilux', 'rav4', 'fortuner', 'land cruiser',
    'focus', 'fiesta', 'ranger', 'ecosport', 'escape',
    'rio', 'cerato', 'sportage', 'sorento', 'picanto',
    'accent', 'tucson', 'santa fe',
    'logan', 'duster', 'sandero',
    'partner', 'berlingo',
    'chevrolet', 'n-300', 'n300', 'dmax', 'luv',
    'toyota', 'ford', 'hyundai', 'kia', 'renault', 'peugeot', 'suzuki',
    'nissan', 'mazda', 'mitsubishi', 'volkswagen', 'vw',
]


def _detect_intent(msg: str):
    """
    Retorna ('oem', code) | ('model', name) | ('general', keyword)
    """
    msg_lower = msg.lower()

    # Detectar modelo de vehículo
    for vehicle in _VEHICLE_KEYWORDS:
        if vehicle in msg_lower:
            return 'model', vehicle

    # Detectar código OEM (secuencia alfanumérica ≥ 6 chars sin espacios)
    oem_match = _OEM_PATTERN.search(msg)
    if oem_match:
        return 'oem', oem_match.group(0)

    # Búsqueda general: quitar palabras conversacionales
    stopwords = {
        'buscar', 'busco', 'tienen', 'tienes', 'quiero', 'necesito',
        'precio', 'cuánto', 'cuanto', 'vale', 'hay', 'el', 'la', 'los',
        'las', 'un', 'una', 'repuesto', 'repuestos', 'de', 'para', 'por',
        'favor', 'oem', 'codigo', 'código', 'referencia',
    }
    words = [w for w in re.split(r'\W+', msg_lower) if w and w not in stopwords]
    keyword = ' '.join(words).strip()
    return 'general', keyword


def chat_with_agent(user_message: str) -> str:
    msg = user_message.lower()

    if 'hola' in msg or 'saludos' in msg:
        return '¡Hola! Soy el Agente Virtual de Repuestos MOM. ¿Qué repuesto estás buscando hoy?'

    if 'ayuda' in msg:
        return (
            'Puedo ayudarte a consultar partes, precios e inventario. '
            'Dime qué buscas, por ejemplo:\n'
            '- "Busco termostato para Aveo"\n'
            '- "Código OEM 96445053"\n'
            '- "¿Tienen pastillas para Hilux?"'
        )

    intent, value = _detect_intent(user_message)

    if not value:
        return '¿Podrías ser más específico con qué repuesto estás buscando?'

    if intent == 'oem':
        items = search_oem(value, limit=5)
        label = f'OEM `{value}`'
    elif intent == 'model':
        items = search_by_model(value, limit=5)
        label = f'vehículo "{value}"'
    else:
        items = search_products(value, limit=5)
        label = f'"{value}"'

    if not items:
        return (
            f'Lo siento, no encontré coincidencias para {label} en nuestro inventario. '
            '¿Tienes el código interno o OEM exacto?'
        )

    response = f'Encontré **{len(items)}** resultado(s) para {label}:\n\n'
    for p in items:
        response += format_product(p) + '\n\n---\n\n'

    response += '¿Deseas buscar algo más?'
    return response
