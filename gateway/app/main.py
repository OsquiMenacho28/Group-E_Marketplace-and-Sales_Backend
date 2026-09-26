import os
import logging
import httpx
from fastapi import FastAPI, Request, Response, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
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

    # Los endpoints de streaming (Server-Sent Events, p. ej. el notificador de
    # sincronización de catálogo RF-08) nunca "terminan" su respuesta, por lo
    # que deben reenviarse con streaming real en lugar de esperar el cuerpo
    # completo con client.request(); de lo contrario la conexión del cliente
    # queda colgada indefinidamente sin recibir ningún evento.
    if path.rstrip("/").endswith("sync-events"):
        return await _forward_streaming(url, request, headers)

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


async def _forward_streaming(url: str, request: Request, headers: dict) -> StreamingResponse:
    """Reenvía una respuesta de streaming (SSE) sin bufferizarla en el gateway."""
    client = httpx.AsyncClient(timeout=None)
    try:
        req = client.build_request(method=request.method, url=url, headers=headers)
        upstream = await client.send(req, stream=True)
    except httpx.ConnectError:
        await client.aclose()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Microservicio de destino no disponible en {url}"
        )

    async def event_iterator():
        try:
            async for chunk in upstream.aiter_raw():
                yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    excluded = {"content-length", "content-encoding", "transfer-encoding", "connection"}
    passthrough_headers = {k: v for k, v in upstream.headers.items() if k.lower() not in excluded}

    return StreamingResponse(
        event_iterator(),
        status_code=upstream.status_code,
        headers=passthrough_headers,
        media_type=upstream.headers.get("content-type", "text/event-stream"),
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
