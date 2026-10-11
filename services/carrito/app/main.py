from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
try:
    from app.routers import router
    from app.cupones_router import router as cupones_router
except (ModuleNotFoundError, ImportError):
    from backend.services.carrito.app.routers import router
    from backend.services.carrito.app.cupones_router import router as cupones_router
from backend.shared.exceptions import MaxiConectaException, maxiconecta_exception_handler

app = FastAPI(
    title="MaxiConecta - Microservicio de Carrito y Checkout",
    description="Carrito persistente en Redis, cupones y bloqueo temporal de stock (RF-13 a RF-21).",
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
# El router de cupones va primero: /cupones no debe capturarse como /{identificador}.
app.include_router(cupones_router)
app.include_router(router)

@app.get("/health", tags=["Salud"])
async def health():
    return {"status": "ok", "service": "ms-carrito", "port": 8003}
