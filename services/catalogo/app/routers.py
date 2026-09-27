import asyncio
import json as _json
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
import base64
import binascii
import re
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from app.schemas import (
    ProductoCreate, ProductoResponse, ProductoUpdate, VarianteResponse, CategoriaResponse,
    SyncCatalogoItem, SyncCatalogoResponse,
    StockDisponibilidadResponse,
    StockSucursal, ProductoStockResumen, BusquedaStockResponse,
)
from backend.shared.database import get_supabase_admin_client
from backend.shared.erp_clients.inventarios import inventarios_client
from backend.shared.redis_client import get_stock_cache, set_stock_cache, STOCK_CACHE_TTL_SECONDS
from backend.shared.security import get_current_user, require_jwt_claims

logger = logging.getLogger("maxiconecta.catalogo")

router = APIRouter(prefix="/api/v1/catalogo", tags=["Catálogo"])

STORAGE_BUCKET = "productos"
MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
DATA_URL_PATTERN = re.compile(r"^data:(image/(?:jpeg|png|webp));base64,([A-Za-z0-9+/=]+)$")

_MOCK_PRODUCTOS = [
    ProductoResponse(
        id=UUID("a0000000-0000-0000-0000-000000000001"),
        sku="LAP-DELL-XPS15",
        nombre="Laptop Dell XPS 15",
        descripcion="Laptop de alta gama con procesador Intel Core i7 y pantalla 4K OLED",
        marca="Dell",
        categoria_id=_MOCK_CATEGORIAS[0].id,
        estado="publicado",
        variantes=[
            VarianteResponse(
                id=UUID("b0000000-0000-0000-0000-000000000001"),
                producto_id=UUID("a0000000-0000-0000-0000-000000000001"),
                sku="LAP-DELL-XPS15-16GB",
                nombre_variante="16GB RAM / 512GB SSD",
                atributos={"ram": "16GB", "almacenamiento": "512GB"},
                precio=Decimal("8999.00"),
                codigo_barras="777123456001"
            )
        ],
        updated_at=datetime(2026, 9, 1, tzinfo=timezone.utc)
    ),
    ProductoResponse(
        id=UUID("a0000000-0000-0000-0000-000000000002"),
        sku="MOU-LOG-MX3S",
        nombre="Mouse Inalámbrico Logitech MX Master 3S",
        descripcion="Mouse ergonómico inalámbrico con scroll electromagnético",
        marca="Logitech",
        categoria_id=_MOCK_CATEGORIAS[0].id,
        estado="publicado",
        variantes=[
            VarianteResponse(
                id=UUID("b0000000-0000-0000-0000-000000000002"),
                producto_id=UUID("a0000000-0000-0000-0000-000000000002"),
                sku="MOU-LOG-MX3S",
                nombre_variante="Grafito",
                atributos={"color": "Grafito"},
                precio=Decimal("799.00"),
                codigo_barras="777123456002"
            )
        ],
        updated_at=datetime(2026, 9, 1, tzinfo=timezone.utc)
    ),
    ProductoResponse(
        id=UUID("a0000000-0000-0000-0000-000000000003"),
        sku="MON-LG-27GP",
        nombre='Monitor Gamer LG UltraGear 27" 165Hz IPS',
        descripcion="Monitor gamer con panel IPS, 165Hz y respuesta 1ms",
        marca="LG",
        categoria_id=_MOCK_CATEGORIAS[1].id,
        estado="publicado",
        variantes=[
            VarianteResponse(
                id=UUID("b0000000-0000-0000-0000-000000000003"),
                producto_id=UUID("a0000000-0000-0000-0000-000000000003"),
                sku="MON-LG-27GP",
                nombre_variante="27 pulgadas",
                atributos={"tamano": "27\""},
                precio=Decimal("2450.00"),
                codigo_barras="777123456003"
            )
        ],
        updated_at=datetime(2026, 9, 1, tzinfo=timezone.utc)
    ),
]

def _client():
    client = get_supabase_admin_client()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase no está configurado para el catálogo",
        )
    return client


def _category_value(value: Any) -> Optional[Dict[str, Any]]:
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _product_response(client: Any, row: Dict[str, Any]) -> ProductoResponse:
    category_result = client.table("categorias").select("id,nombre,descripcion,padre_id,atributos_dinamicos,activo").eq("id", row["categoria_id"]).limit(1).execute()
    variants = client.table("variantes").select("*").eq("producto_id", row["id"]).order("created_at").execute().data
    images = client.table("imagenes_producto").select("*").eq("producto_id", row["id"]).order("orden").execute().data
    primary_variant = variants[0] if variants else {}
    return ProductoResponse.model_validate(
        {
            **row,
            "precio": primary_variant.get("precio", 0),
            "categorias": _category_value(category_result.data),
            "variantes": variants,
            "imagenes_producto": images,
        }
    )


def _decode_image(data_url: str) -> tuple[str, bytes]:
    match = DATA_URL_PATTERN.match(data_url)
    if not match:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Solo se admiten imágenes JPEG, PNG o WebP codificadas correctamente",
        )
    try:
        image_bytes = base64.b64decode(match.group(2), validate=True)
    except binascii.Error as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="La imagen no es base64 válida") from error
    if not image_bytes or len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Cada imagen debe pesar como máximo 5 MB",
        )
    return match.group(1), image_bytes


def _ensure_bucket(client: Any) -> None:
    buckets = client.storage.list_buckets()
    if not any(bucket.name == STORAGE_BUCKET for bucket in buckets):
        client.storage.create_bucket(STORAGE_BUCKET, {"public": True, "file_size_limit": MAX_IMAGE_BYTES})


# ------------------------------------------------------------------------------
# RF-08: Suscriptores en memoria para el notificador SSE de cambios de catálogo.
# Cada terminal POS conectada mantiene una cola propia; al mutar un producto se
# difunde el evento a todas las colas activas (broadcast simple in-process).
# ------------------------------------------------------------------------------
_SYNC_SUBSCRIBERS: List["asyncio.Queue[Dict[str, Any]]"] = []

async def _broadcast_catalogo_event(evento: Dict[str, Any]) -> None:
    evento_completo = {**evento, "emitido_en": datetime.now(timezone.utc).isoformat()}
    for cola in list(_SYNC_SUBSCRIBERS):
        await cola.put(evento_completo)

# ------------------------------------------------------------------------------
# Consulta Rápida de Stock Multi-Sucursal (Modal F3): caché de lectura en
# memoria de muy corta duración para optimizar búsquedas repetidas del mismo
# término mientras el cajero/administrador escribe.
# ------------------------------------------------------------------------------
_STOCK_MULTISUCURSAL_CACHE: Dict[str, Dict[str, Any]] = {}
_STOCK_MULTISUCURSAL_CACHE_TTL = 15  # segundos

@router.get("/categorias", response_model=List[CategoriaResponse])
async def listar_categorias():
    result = _client().table("categorias").select("id,nombre,descripcion,padre_id,atributos_dinamicos,activo").eq("activo", True).order("nombre").execute()
    return result.data


@router.get("/productos", response_model=List[ProductoResponse])
async def listar_productos(
    q: Optional[str] = Query(None, description="Texto de búsqueda facetada RF-06"),
    categoria_id: Optional[UUID] = Query(None),
    precio_min: Optional[Decimal] = Query(None),
    precio_max: Optional[Decimal] = Query(None),
):
    client = _client()
    query = client.table("productos").select("*").eq("estado", "publicado")
    if q:
        query = query.or_(f"nombre.ilike.%{q}%,sku.ilike.%{q}%,marca.ilike.%{q}%")
    if categoria_id:
        query = query.eq("categoria_id", str(categoria_id))
    result = query.order("created_at", desc=True).execute()
    products = [_product_response(client, row) for row in result.data]
    if precio_min is not None:
        products = [product for product in products if product.precio >= precio_min]
    if precio_max is not None:
        products = [product for product in products if product.precio <= precio_max]
    return products


@router.get("/productos/{product_id}", response_model=ProductoResponse)
async def obtener_producto(product_id: UUID):
    client = _client()
    result = client.table("productos").select("*").eq("id", str(product_id)).single().execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")
    return _product_response(client, result.data)

@router.get("/productos/buscar-stock", response_model=BusquedaStockResponse)
async def buscar_stock_multisucursal(
    q: str = Query(..., min_length=1, description="SKU o nombre de producto a buscar")
):
    """
    [INT] Consulta de disponibilidad multi-sucursal con caché de lectura
    optimizada (SIMULA INTEGRACIÓN por el momento vía InventariosClient).
    [BE] Búsqueda rápida de producto por SKU/nombre y desglose por sucursal,
    usada por el modal de consulta rápida (atajo F3) en el POS.
    """
    q_norm = q.strip().lower()
    ahora = datetime.now(timezone.utc).timestamp()

    cacheado = _STOCK_MULTISUCURSAL_CACHE.get(q_norm)
    if cacheado and (ahora - cacheado["ts"]) < _STOCK_MULTISUCURSAL_CACHE_TTL:
        return BusquedaStockResponse(**cacheado["data"], origen_cache=True)

    coincidencias = [
        p for p in _MOCK_PRODUCTOS
        if q_norm in p.nombre.lower()
        or q_norm in p.sku.lower()
        or any(q_norm in v.sku.lower() for v in p.variantes)
    ]

    resultados: List[ProductoStockResumen] = []
    for p in coincidencias:
        sku_ref = p.variantes[0].sku if p.variantes else p.sku
        data = await inventarios_client.consultar_disponibilidad_multisucursal(sku_ref)
        sucursales = [StockSucursal(**s) for s in data.get("sucursales", [])]
        resultados.append(ProductoStockResumen(
            producto_id=p.id,
            sku=sku_ref,
            nombre=p.nombre,
            stock_total=sum(s.stock_disponible for s in sucursales),
            sucursales=sucursales,
        ))

    respuesta = {"query": q, "resultados": [r.model_dump() for r in resultados]}
    _STOCK_MULTISUCURSAL_CACHE[q_norm] = {"ts": ahora, "data": respuesta}
    return BusquedaStockResponse(**respuesta, origen_cache=False)

@router.get("/productos/{id}", response_model=ProductoResponse)
async def obtener_producto(id: UUID):
    """RF-01: Detalle de producto con variantes."""
    for p in _MOCK_PRODUCTOS:
        if p.id == id:
            return p
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")

@router.post("/productos", response_model=ProductoResponse, status_code=status.HTTP_201_CREATED)
@require_jwt_claims("sub", allowed_roles={"administrador", "gerente_comercial"})
async def crear_producto(
    payload: ProductoCreate,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    client = _client()
    category = client.table("categorias").select("id").eq("id", str(payload.categoria_id)).limit(1).execute()
    if not category.data:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="La categoría seleccionada no existe")

    existing = client.table("productos").select("id").eq("sku", payload.sku.upper()).limit(1).execute()
    if existing.data:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya existe un producto con ese SKU")

    prepared_images = [
        (image, *_decode_image(image.data_url))
        for image in payload.imagenes
    ]
    
    # nuevo_prod = ProductoResponse(
    #     id=prod_id,
    #     sku=payload.sku,
    #     nombre=payload.nombre,
    #     descripcion=payload.descripcion,
    #     marca=payload.marca,
    #     categoria_id=payload.categoria_id,
    #     estado="publicado",
    #     variantes=variantes_res,
    #     updated_at=datetime.now(timezone.utc)
    # )
    # _MOCK_PRODUCTOS.append(nuevo_prod)
    # await _broadcast_catalogo_event({
    #     "tipo": "producto_creado",
    #     "producto_id": str(nuevo_prod.id),
    #     "sku": nuevo_prod.sku,
    #     "nombre": nuevo_prod.nombre,
    #     "precio": float(variantes_res[0].precio) if variantes_res else None,
    #     "estado": nuevo_prod.estado,
    #     "updated_at": nuevo_prod.updated_at.isoformat(),
    # })
    # return nuevo_prod

    product = client.table("productos").insert(
        {
            "sku": payload.sku.upper(),
            "nombre": payload.nombre,
            "descripcion": payload.descripcion,
            "marca": payload.marca,
            "categoria_id": str(payload.categoria_id),
            "estado": "publicado",
        }
    ).execute().data[0]
    product_id = product["id"]

    variants = payload.variantes or [
        {
            "sku": f"{payload.sku.upper()}-BASE",
            "nombre_variante": "Configuración principal",
            "atributos": {},
            "precio": payload.precio,
            "precio_costo": Decimal("0"),
        }
    ]
    for variant in variants:
        variant_data = variant.model_dump(mode="json") if hasattr(variant, "model_dump") else variant
        client.table("variantes").insert({"producto_id": product_id, **variant_data}).execute()

    if prepared_images:
        _ensure_bucket(client)
        for index, (image, content_type, content) in enumerate(prepared_images):
            extension = ALLOWED_IMAGE_TYPES[content_type]
            path = f"productos/{product_id}/{uuid4()}.{extension}"
            client.storage.from_(STORAGE_BUCKET).upload(path, content, {"content-type": content_type, "upsert": "false"})
            image_url = client.storage.from_(STORAGE_BUCKET).get_public_url(path)
            client.table("imagenes_producto").insert(
                {"producto_id": product_id, "url": image_url, "es_principal": index == 0, "orden": index}
            ).execute()

    created = client.table("productos").select("*").eq("id", product_id).single().execute()
    return _product_response(client, created.data)


@router.patch("/productos/{id}", response_model=ProductoResponse)
async def actualizar_producto(id: UUID, payload: ProductoUpdate):
    """
    RF-08: Actualiza datos/precio de un producto y dispara el evento de
    sincronización multicanal (notificador SSE) hacia las terminales POS
    conectadas, para mantener consistencia de datos y precios entre canales.
    """
    for p in _MOCK_PRODUCTOS:
        if p.id == id:
            if payload.nombre is not None:
                p.nombre = payload.nombre
            if payload.descripcion is not None:
                p.descripcion = payload.descripcion
            if payload.marca is not None:
                p.marca = payload.marca
            if payload.estado is not None:
                p.estado = payload.estado
            if payload.precio is not None and p.variantes:
                p.variantes[0].precio = payload.precio
            p.updated_at = datetime.now(timezone.utc)

            await _broadcast_catalogo_event({
                "tipo": "producto_actualizado",
                "producto_id": str(p.id),
                "sku": p.sku,
                "nombre": p.nombre,
                "precio": float(p.variantes[0].precio) if p.variantes else None,
                "estado": p.estado,
                "updated_at": p.updated_at.isoformat(),
            })
            return p
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")

# ==============================================================================
# RF-08 — SINCRONIZACIÓN MULTICANAL (WEB <-> POS)
# ==============================================================================

@router.get("/sync-catalogo", response_model=SyncCatalogoResponse)
async def sync_catalogo_delta(
    since: Optional[datetime] = Query(
        None, description="Timestamp ISO 8601 de la última sincronización local (se devuelven cambios con updated_at posterior)"
    ),
    cursor: Optional[str] = Query(None, description="Cursor de paginación devuelto por la página anterior"),
    page_size: int = Query(20, ge=1, le=100, description="Tamaño de página para la sincronización por lotes"),
):
    """
    RF-08 [BE]: Endpoint delta de sincronización de catálogo con paginación por
    timestamp `updated_at`. Las terminales POS (o cualquier otro canal) llaman
    a este endpoint pasando la fecha de su última sincronización exitosa (`since`)
    y reciben únicamente los productos creados/modificados después de esa fecha,
    en páginas de `page_size` elementos ordenadas ascendentemente.
    """
    candidatos = sorted(_MOCK_PRODUCTOS, key=lambda p: p.updated_at)

    if since is not None:
        since_utc = since if since.tzinfo else since.replace(tzinfo=timezone.utc)
        candidatos = [p for p in candidatos if p.updated_at > since_utc]

    offset = int(cursor) if cursor and cursor.isdigit() else 0
    pagina = candidatos[offset: offset + page_size]
    hay_mas = (offset + page_size) < len(candidatos)
    siguiente_cursor = str(offset + page_size) if hay_mas else None

    items = [
        SyncCatalogoItem(
            id=p.id,
            sku=p.sku,
            nombre=p.nombre,
            precio_referencia=(p.variantes[0].precio if p.variantes else Decimal("0")),
            estado=p.estado,
            updated_at=p.updated_at,
            accion="baja" if p.estado == "descontinuado" else "upsert",
        )
        for p in pagina
    ]

    return SyncCatalogoResponse(
        items=items,
        cursor_siguiente=siguiente_cursor,
        hay_mas=hay_mas,
        servidor_timestamp=datetime.now(timezone.utc),
    )

@router.get("/sync-events")
async def sync_events_stream():
    """
    RF-08 [BE]: Notificador de cambios de catálogo hacia terminales POS
    conectadas, mediante Server-Sent Events (SSE). Cada terminal abre una
    conexión persistente a este endpoint y recibe en tiempo real los eventos
    `catalogo-actualizado` emitidos por `crear_producto`/`actualizar_producto`,
    sin necesidad de hacer polling constante al endpoint de sincronización.
    """
    cola: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue()
    _SYNC_SUBSCRIBERS.append(cola)
    logger.info(f"Nueva terminal POS suscrita a sync-events (total activas: {len(_SYNC_SUBSCRIBERS)})")

    async def event_generator():
        try:
            yield f"event: connected\ndata: {_json.dumps({'mensaje': 'Suscrito a cambios de catálogo en tiempo real'})}\n\n"
            while True:
                evento = await cola.get()
                yield f"event: catalogo-actualizado\ndata: {_json.dumps(evento, default=str)}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            if cola in _SYNC_SUBSCRIBERS:
                _SYNC_SUBSCRIBERS.remove(cola)
            logger.info(f"Terminal POS desconectada de sync-events (total activas: {len(_SYNC_SUBSCRIBERS)})")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )

# ==============================================================================
# RF-07 — DISPONIBILIDAD DE STOCK EN TIEMPO REAL (RIO-INV-01 + CACHÉ REDIS)
# ==============================================================================

@router.get("/stock/{sku}", response_model=StockDisponibilidadResponse)
async def consultar_stock(sku: str, sucursal_id: Optional[str] = None):
    """
    RF-07: Consulta la disponibilidad de stock en tiempo real vía RIO-INV-01.
    Antes de llamar al ERP de Inventarios, intenta resolver desde una caché en
    Redis con TTL corto (30s por defecto) para mitigar la latencia del ERP
    externo ante consultas repetidas del mismo SKU/sucursal.
    """
    cacheado = await get_stock_cache(sku, sucursal_id)
    if cacheado is not None:
        return StockDisponibilidadResponse(**cacheado, origen="cache")

    data = await inventarios_client.consultar_disponibilidad(sku, sucursal_id)
    resultado = {
        "sku": sku,
        "sucursal_id": sucursal_id,
        "stock_disponible": int(data.get("stock_disponible", 0)),
        "modo": data.get("modo"),
    }
    await set_stock_cache(sku, resultado, sucursal_id=sucursal_id, ttl_seconds=STOCK_CACHE_TTL_SECONDS)
    return StockDisponibilidadResponse(**resultado, origen="erp")

# ==============================================================================
# CONSULTA RÁPIDA DE STOCK MULTI-SUCURSAL (MODAL F3)
# ==============================================================================


