# ─────────────────────────────────────────────────────────────────
# IMPORTS Y CONFIGURACIÓN
# ─────────────────────────────────────────────────────────────────
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
from typing import Optional
import uuid
import os

load_dotenv()

from backend.agent import chat_with_agent, analyze_image
from backend.odoo_client import get_catalog, get_product_detail, serialize_catalog_row
from backend.voice import transcribe_audio, synthesize_speech

app = FastAPI(title="Agente MOM API")

# ─────────────────────────────────────────────────────────────────
# MODELOS DE PETICIÓN
# ─────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class SynthesizeRequest(BaseModel):
    text: str


# ─────────────────────────────────────────────────────────────────
# ARCHIVOS ESTÁTICOS (frontend)
# ─────────────────────────────────────────────────────────────────
frontend_path = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory="frontend"), name="static")


# ─────────────────────────────────────────────────────────────────
# RUTAS — SISTEMA
# ─────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok"}


# ─────────────────────────────────────────────────────────────────
# RUTAS — AGENTE DE CHAT
# ─────────────────────────────────────────────────────────────────
@app.post("/api/chat")
async def api_chat(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())
    response_text = chat_with_agent(req.message, session_id)
    return {"reply": response_text, "session_id": session_id}


# ─────────────────────────────────────────────────────────────────
# RUTAS — IMAGEN (Gemini Vision)
# ─────────────────────────────────────────────────────────────────
@app.post("/api/chat/image")
async def api_chat_image(
    image: UploadFile = File(...),
    message: str = "",
    session_id: str = "",
):
    image_bytes = await image.read()
    mime_type   = image.content_type or "image/jpeg"
    sid         = session_id or str(uuid.uuid4())
    reply       = analyze_image(image_bytes, mime_type, message, sid)
    return {"reply": reply, "session_id": sid}


# ─────────────────────────────────────────────────────────────────
# RUTAS — VOZ (Speech-to-Text / Text-to-Speech)
# ─────────────────────────────────────────────────────────────────
@app.post("/api/voice/transcribe")
async def api_transcribe(audio: UploadFile = File(...)):
    audio_bytes = await audio.read()
    mime_type   = audio.content_type or "audio/webm"
    try:
        text = transcribe_audio(audio_bytes, mime_type)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error en transcripción: {exc}")
    return {"text": text}


@app.post("/api/voice/synthesize")
async def api_synthesize(req: SynthesizeRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Texto vacío")
    try:
        audio_bytes = synthesize_speech(req.text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error en síntesis: {exc}")
    return Response(content=audio_bytes, media_type="audio/mpeg")


# ─────────────────────────────────────────────────────────────────
# RUTAS — CATÁLOGO E INVENTARIO
# ─────────────────────────────────────────────────────────────────
@app.get("/api/catalog")
async def api_catalog(page: int = 1, limit: int = 50, solo_con_stock: bool = False):
    result = get_catalog(page=page, limit=limit, solo_con_stock=solo_con_stock)
    return {
        "products": [serialize_catalog_row(p) for p in result["products"]],
        "total":    result["total"],
        "page":     page,
        "limit":    limit,
    }


@app.get("/api/product/{product_id}")
async def api_product_detail(product_id: int):
    p = get_product_detail(product_id)
    if not p:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return p


# ─────────────────────────────────────────────────────────────────
# RUTA RAÍZ — SIRVE EL FRONTEND
# ─────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def read_root():
    index_file = os.path.join(frontend_path, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), status_code=200)
    return HTMLResponse(content="<h1>Frontend no encontrado</h1><p>Asegúrate de crear frontend/index.html.</p>", status_code=404)


# ─────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
