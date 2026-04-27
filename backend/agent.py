import os
import time
import logging
import google.generativeai as genai

from backend.odoo_client import (
    search_products,
    search_oem,
    search_by_model,
    format_product,
)

log = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
MODEL_ID       = os.environ.get('GEMINI_MODEL', 'gemini-1.5-flash')

genai.configure(api_key=GEMINI_API_KEY)

SYSTEM_PROMPT = """Eres el Asistente Virtual de Repuestos MOM, una tienda especializada en repuestos automotrices ubicada en Chile.

CONTEXTO:
- El inventario está gestionado en Odoo 19
- Los precios están en pesos chilenos (CLP)
- El stock indica unidades disponibles en bodega
- Los atributos técnicos disponibles son: Código OEM, Modelo, Tipo de vehículo, Diámetro interior, Diámetro externo, Espesor

MARCAS Y MODELOS QUE MANEJAMOS:
Chevrolet (Aveo, Sail, Spark, Corsa, Cruze, Tracker, N-300, D-Max, LUV), Toyota (Corolla, Yaris, Hilux, RAV4, Fortuner), Ford (Focus, Fiesta, Ranger, EcoSport), Hyundai (Accent, Tucson, Santa Fe), Kia (Rio, Cerato, Sportage, Sorento, Picanto), Renault (Logan, Duster, Sandero), Peugeot (Partner, Berlingo), Suzuki, Nissan, Mazda, Mitsubishi, Volkswagen.

INSTRUCCIONES:
1. Analiza la consulta del cliente con precisión — identifica el repuesto, la marca Y el modelo específico del vehículo
2. Usa las herramientas para buscar en el inventario antes de responder
3. Presenta resultados de forma clara: nombre, código, stock y precio
4. Si no hay stock (stock=0), menciónalo explícitamente
5. Si no hay resultados, sugiere una búsqueda alternativa
6. Responde siempre en español, de forma profesional y concisa
7. Recuerda el contexto de la conversación — si el cliente ya mencionó un modelo de vehículo, úsalo en búsquedas posteriores
"""

_tools = genai.protos.Tool(function_declarations=[
    genai.protos.FunctionDeclaration(
        name="buscar_producto",
        description="Busca repuestos en el inventario por nombre de la pieza o código interno. Usar para búsquedas generales cuando no se menciona marca/modelo ni código OEM.",
        parameters=genai.protos.Schema(
            type=genai.protos.Type.OBJECT,
            properties={
                "keyword": genai.protos.Schema(
                    type=genai.protos.Type.STRING,
                    description="Nombre del repuesto a buscar (ej: 'amortiguador trasero', 'termostato', 'pastillas freno')"
                )
            },
            required=["keyword"]
        )
    ),
    genai.protos.FunctionDeclaration(
        name="buscar_oem",
        description="Busca un repuesto por su código OEM (referencia del fabricante original). Usar cuando el cliente proporciona un código alfanumérico con números (ej: 96445053, AB12345).",
        parameters=genai.protos.Schema(
            type=genai.protos.Type.OBJECT,
            properties={
                "codigo_oem": genai.protos.Schema(
                    type=genai.protos.Type.STRING,
                    description="Código OEM del repuesto (ej: '96445053', '12380318')"
                )
            },
            required=["codigo_oem"]
        )
    ),
    genai.protos.FunctionDeclaration(
        name="buscar_por_modelo",
        description="Busca repuestos compatibles con un modelo o marca de vehículo específico. Usar cuando el cliente menciona marca, modelo o tipo de vehículo.",
        parameters=genai.protos.Schema(
            type=genai.protos.Type.OBJECT,
            properties={
                "modelo": genai.protos.Schema(
                    type=genai.protos.Type.STRING,
                    description="Marca o modelo del vehículo (ej: 'N-300', 'Hilux', 'Aveo', 'Chevrolet')"
                ),
                "repuesto": genai.protos.Schema(
                    type=genai.protos.Type.STRING,
                    description="Tipo de repuesto que busca (ej: 'amortiguador', 'termostato'). Opcional."
                )
            },
            required=["modelo"]
        )
    ),
])

_model = genai.GenerativeModel(
    MODEL_ID,
    system_instruction=SYSTEM_PROMPT,
    tools=[_tools],
)

# Sesiones activas: {session_id: {"chat": ChatSession, "last_used": float}}
_sessions: dict = {}
_SESSION_TTL = 3600  # 1 hora


def _cleanup_sessions():
    now = time.time()
    expired = [sid for sid, s in _sessions.items() if now - s["last_used"] > _SESSION_TTL]
    for sid in expired:
        del _sessions[sid]


def _get_or_create_chat(session_id: str):
    _cleanup_sessions()
    if session_id not in _sessions:
        _sessions[session_id] = {"chat": _model.start_chat(), "last_used": time.time()}
    else:
        _sessions[session_id]["last_used"] = time.time()
    return _sessions[session_id]["chat"]


def _execute_tool(name: str, args: dict) -> str:
    if name == "buscar_producto":
        keyword = args.get("keyword", "")
        items = search_products(keyword, limit=5)
    elif name == "buscar_oem":
        items = search_oem(args.get("codigo_oem", ""), limit=5)
    elif name == "buscar_por_modelo":
        modelo = args.get("modelo", "")
        repuesto = args.get("repuesto", "")
        keyword = f"{repuesto} {modelo}".strip() if repuesto else modelo
        items = search_by_model(keyword, limit=5)
    else:
        return "Herramienta no reconocida."

    if not items:
        return "No se encontraron productos en el inventario para esa búsqueda."

    result = f"Se encontraron {len(items)} resultado(s):\n\n"
    for p in items:
        result += format_product(p) + "\n\n---\n\n"
    return result


def chat_with_agent(user_message: str, session_id: str = "default") -> str:
    try:
        chat = _get_or_create_chat(session_id)
        response = chat.send_message(user_message)

        for _ in range(5):
            function_calls = [
                part.function_call
                for part in response.candidates[0].content.parts
                if hasattr(part, 'function_call') and part.function_call.name
            ]

            if not function_calls:
                break

            function_responses = []
            for fc in function_calls:
                tool_result = _execute_tool(fc.name, dict(fc.args))
                function_responses.append(
                    genai.protos.Part(
                        function_response=genai.protos.FunctionResponse(
                            name=fc.name,
                            response={"result": tool_result}
                        )
                    )
                )

            response = chat.send_message(function_responses)

        return response.text

    except Exception as e:
        log.error("Error en chat_with_agent: %s", e)
        _sessions.pop(session_id, None)
        return "Lo siento, tuve un problema procesando tu consulta. Por favor intenta nuevamente."
