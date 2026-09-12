import os
import logging
import httpx
from fastapi import FastAPI, Request, Response, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from backend.shared.config import settings
from backend.shared.security import get_current_user, require_role, decode_access_token
from backend.shared.exceptions import MaxiConectaException, maxiconecta_exception_handler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("maxiconecta.gateway")

app = FastAPI(
    title="MaxiConecta - API Gateway",
    description="Punto de entrada unificado y seguridad para los microservicios de MaxiConecta (Grupo E).",
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

# ------------------------------------------------------------------------------
# RUTA DE SALUD
# ------------------------------------------------------------------------------
@app.get("/health", tags=["Sistema"])
async def health_check():
    return {
        "status": "healthy",
        "service": "api-gateway",
        "environment": settings.ENVIRONMENT,
        "microservices": {
            "catalogo": settings.MS_CATALOGO_URL,
            "pos": settings.MS_POS_URL,
            "carrito": settings.MS_CARRITO_URL,
            "clientes": settings.MS_CLIENTES_URL,
            "ordenes": settings.MS_ORDENES_URL,
            "reportes": settings.MS_REPORTES_URL
        }
    }

# ------------------------------------------------------------------------------
# PROXY INVERSO / REENVÍO A MICROSERVICIOS
# ------------------------------------------------------------------------------
async def forward_request(target_base_url: str, request: Request) -> Response:
    """Reenvía la petición al microservicio correspondiente preservando headers y body."""
    path = request.url.path
    query = request.url.query
    url = f"{target_base_url}{path}"
    if query:
        url = f"{url}?{query}"

    headers = dict(request.headers)
    headers.pop("host", None)

    body = await request.body()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.request(
                method=request.method,
                url=url,
                headers=headers,
                content=body
            )
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers=dict(resp.headers),
                media_type=resp.headers.get("content-type")
            )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Microservicio de destino no disponible en {target_base_url}"
        )

# Mapeo de prefijos a URLs de microservicios
@app.api_route("/api/v1/catalogo/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], tags=["Catálogo"])
async def proxy_catalogo(path: str, request: Request):
    return await forward_request(settings.MS_CATALOGO_URL, request)

@app.api_route("/api/v1/pos/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], tags=["Punto de Venta"])
async def proxy_pos(path: str, request: Request):
    # Opcional: verificación de token para cajero
    return await forward_request(settings.MS_POS_URL, request)

@app.api_route("/api/v1/carrito/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], tags=["Carrito y Checkout"])
async def proxy_carrito(path: str, request: Request):
    return await forward_request(settings.MS_CARRITO_URL, request)

@app.api_route("/api/v1/clientes/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], tags=["Clientes"])
async def proxy_clientes(path: str, request: Request):
    return await forward_request(settings.MS_CLIENTES_URL, request)

@app.api_route("/api/v1/ordenes/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], tags=["Órdenes y Ventas"])
async def proxy_ordenes(path: str, request: Request):
    return await forward_request(settings.MS_ORDENES_URL, request)

@app.api_route("/api/v1/reportes/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], tags=["Reportes y Analítica"])
async def proxy_reportes(path: str, request: Request):
    return await forward_request(settings.MS_REPORTES_URL, request)
