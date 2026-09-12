from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import router
from backend.shared.exceptions import MaxiConectaException, maxiconecta_exception_handler

app = FastAPI(
    title="MaxiConecta - Microservicio de Clientes",
    description="Identidad, perfiles, direcciones y fidelización con CRM (RF-22 a RF-26).",
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
    return {"status": "ok", "service": "ms-clientes", "port": 8004}
