from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import router
from backend.shared.exceptions import MaxiConectaException, maxiconecta_exception_handler

app = FastAPI(
    title="MaxiConecta - Microservicio de Catálogo",
    description="Gestión de catálogo, variantes, precios y disponibilidad (RF-01 a RF-08).",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(MaxiConectaException, maxiconecta_exception_handler)
app.include_router(router)

@app.get("/health", tags=["Salud"])
async def health():
    return {"status": "ok", "service": "ms-catalogo", "port": 8001}
