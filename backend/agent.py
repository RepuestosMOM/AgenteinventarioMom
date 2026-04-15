import re
from backend.odoo_client import search_products

def chat_with_agent(user_message: str) -> str:
    # Lógica de agente conversacional muy básica (basada en palabras clave)
    # Lista para cuando se desee integrar OpenAI o Gemini
    
    msg = user_message.lower()
    
    if "hola" in msg or "saludos" in msg:
        return "¡Hola! Soy el Agente Virtual de Repuestos MOM. ¿Qué repuesto estás buscando hoy?"
        
    if "ayuda" in msg:
        return "Puedo ayudarte a consultar partes, precios e inventario. Simplemente dime qué buscas, por ejemplo: '¿Tienen termostatos?' o 'Busco código 020621057'."

    # Buscar palabras clave "buscar", "tienen", "repuesto", etc.
    # Extracción burda de intención: quitar las palabras conversacionales
    stopwords = ["buscar", "busco", "tienen", "tienes", "quiero", "necesito", "precio", "cuánto", "cuanto", "vale", "hay", "el", "la", "los", "las", "un", "una", "repuesto", "repuestos", "de", "para", "por", "favor"]
    
    words = [w for w in re.split('\W+', msg) if w and w not in stopwords]
    keyword = " ".join(words).strip()
    
    if not keyword:
        return "¿Podrías ser más específico con qué repuesto estás buscando?"
        
    # Consultar Odoo
    items = search_products(keyword, limit=5)
    
    if not items:
        return f"Lo siento, he buscado en nuestro inventario pero no encontré ninguna coincidencia para '{keyword}'. ¿Quizás tengas el código de barra exacto?"
        
    # Formatear la respuesta
    response = f"He encontrado {len(items)} resultados para '{keyword}':\n\n"
    for p in items:
        code = p.get('default_code', 'Sin código')
        name = p.get('name', 'Sin nombre')
        price = p.get('list_price', 0)
        stock = p.get('qty_available', 0)
        response += f"⚙️ **{name}** (Code: {code})\n"
        response += f"   ➤ Stock: **{stock}** unidades | Precio: ${price:,.0f} CLP\n\n"
        
    response += "¿Deseas buscar algo más?"
    return response
