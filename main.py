from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from backend.agent import chat_with_agent
import os

app = FastAPI(title="Agente MOM API")


@app.get("/health")
def health():
    return {"status": "ok"}

# Modelo de datos para la API
class ChatRequest(BaseModel):
    message: str

# Montar frontend estático si existe la carpeta
frontend_path = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.post("/api/chat")
async def api_chat(req: ChatRequest):
    # Enviar el mensaje al agente
    response_text = chat_with_agent(req.message)
    return {"reply": response_text}

@app.get("/", response_class=HTMLResponse)
async def read_root():
    # Servir el archivo index.html
    index_file = os.path.join(frontend_path, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), status_code=200)
    return HTMLResponse(content="<h1>Frontend no encontrado</h1><p>Asegúrate de crear frontend/index.html.</p>", status_code=404)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
