from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
try:
    from app.routers import router
    from app.routers_facturacion import router as facturacion_router
except (ModuleNotFoundError, ImportError):
    from backend.services.ordenes.app.routers import router
    from backend.services.ordenes.app.routers_facturacion import router as facturacion_router
from backend.shared.exceptions import MaxiConectaException, maxiconecta_exception_handler

app = FastAPI(
    title="MaxiConecta - Microservicio de Órdenes y Ventas",
    description="Máquina de estados, cancelaciones, reversiones y cotizaciones B2B (RF-27 a RF-39).",
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
app.include_router(facturacion_router)

@app.get("/health", tags=["Salud"])
async def health():
    return {"status": "ok", "service": "ms-ordenes", "port": 8005}
