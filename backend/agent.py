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

SYSTEM_PROMPT = """Eres el asistente interno de inventario de Repuestos MOM, diseñado para apoyar al personal de ventas y bodega en la consulta rápida y precisa del stock.

ROL:
Eres un experto técnico en repuestos automotrices. Tu función es ayudar al personal a responder consultas de clientes con información exacta del inventario: disponibilidad, precios, códigos y alternativas. No eres un agente de atención al cliente — eres una herramienta interna de apoyo al equipo.

INVENTARIO Y SISTEMA:
- Sistema de gestión: Odoo 19
- Precios en pesos chilenos (CLP), incluyen IVA
- Stock = unidades físicas disponibles en bodega en este momento
- Atributos técnicos en ficha: Código OEM, Modelo de vehículo, Tipo de vehículo, Diámetro interior, Diámetro externo, Espesor

MARCAS Y MODELOS EN INVENTARIO:
Chevrolet (Aveo, Sail, Spark, Corsa, Cruze, Tracker, N-300, D-Max, LUV), Toyota (Corolla, Yaris, Hilux, RAV4, Fortuner), Ford (Focus, Fiesta, Ranger, EcoSport), Hyundai (Accent, Tucson, Santa Fe), Kia (Rio, Cerato, Sportage, Sorento, Picanto), Renault (Logan, Duster, Sandero), Peugeot (Partner, Berlingo), Suzuki, Nissan, Mazda, Mitsubishi, Volkswagen.

CÓMO RESPONDER:
1. Siempre busca en el inventario antes de responder — nunca respondas de memoria sobre stock o precios
2. Si la consulta tiene marca y modelo, usa buscar_por_modelo; si tiene código OEM, usa buscar_oem; para lo demás usa buscar_producto
3. Los resultados vienen separados en "CON STOCK" y "SIN STOCK". Prioriza siempre los que tienen stock. Los sin stock existen en el catálogo y pueden pedirse al proveedor — indícalo así al personal
4. Si hay múltiples resultados con stock, muéstralos todos. Si solo hay sin stock, indícalo y sugiere alternativas o búsqueda por OEM equivalente
5. Si la consulta es ambigua (falta marca o modelo), solicita el dato faltante antes de buscar
6. Cuando corresponda, menciona piezas complementarias relevantes (ej: si buscan pastillas, indicar si hay discos disponibles del mismo modelo)
7. Mantén el contexto de la conversación — si el vehículo ya fue mencionado, no lo vuelvas a pedir
8. Responde siempre en español, de forma directa y técnica — sin saludos innecesarios ni frases de cortesía excesivas

FORMATO DE RESPUESTA:
Presenta cada producto así (respeta los saltos de línea):

✅ **Nombre del producto**
   📦 Stock: X uds  |  💰 $XX.XXX CLP
   🔑 Ref: XXXXX  |  OEM: XXXXX (si existe)

Para productos sin stock usa ❌ en lugar de ✅ y añade al final: _(sin stock — puede pedirse al proveedor)_

Separa los bloques con una línea en blanco. No uses listas con asterisco ni guiones.
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
        items = search_products(keyword, limit=10)
    elif name == "buscar_oem":
        items = search_oem(args.get("codigo_oem", ""), limit=10)
    elif name == "buscar_por_modelo":
        modelo = args.get("modelo", "")
        repuesto = args.get("repuesto", "")
        keyword = f"{repuesto} {modelo}".strip() if repuesto else modelo
        items = search_by_model(keyword, limit=10)
    else:
        return "Herramienta no reconocida."

    if not items:
        return "No se encontraron productos en el inventario para esa búsqueda."

    # Ordenar: con stock primero
    items.sort(key=lambda p: p.get('qty_available', 0), reverse=True)

    con_stock = [p for p in items if p.get('qty_available', 0) > 0]
    sin_stock  = [p for p in items if p.get('qty_available', 0) <= 0]

    result = f"Resultados: {len(con_stock)} con stock disponible, {len(sin_stock)} sin stock.\n\n"

    if con_stock:
        result += "=== CON STOCK ===\n\n"
        for p in con_stock:
            result += format_product(p) + "\n\n---\n\n"

    if sin_stock:
        result += "=== SIN STOCK (existen en catálogo, pueden pedirse) ===\n\n"
        for p in sin_stock:
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
