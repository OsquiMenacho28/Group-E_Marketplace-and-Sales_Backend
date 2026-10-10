import asyncio
import base64
import binascii
import json as _json
import logging
import re
import unicodedata
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4, uuid5

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse

try:
    from app.schemas import (
        CategoriaCreate,
        CategoriaUpdate,
        CategoriaResponse,
        ProductoCreate,
        ProductoResponse,
        ProductoUpdate,
        VarianteResponse,
        ImagenProductoResponse,
        FacetItem,
        RangoPrecioFacet,
        FacetasCatalogo,
        BusquedaFacetadaResponse,
        SugerenciaItem,
        SyncCatalogoItem,
        SyncCatalogoResponse,
        SyncStatusResponse,
        StockDisponibilidadResponse,
        StockSucursal,
        ProductoStockResumen,
        BusquedaStockResponse,
        PrecioResolucionResponse,
        ListaPrecioCreate,
        ListaPrecioUpdate,
        ListaPrecioResponse,
        PrecioItemCreate,
        PrecioItemResponse,
    )
except (ModuleNotFoundError, ImportError):
    from backend.services.catalogo.app.schemas import (
        CategoriaCreate,
        CategoriaUpdate,
        CategoriaResponse,
        ProductoCreate,
        ProductoResponse,
        ProductoUpdate,
        VarianteResponse,
        ImagenProductoResponse,
        FacetItem,
        RangoPrecioFacet,
        FacetasCatalogo,
        BusquedaFacetadaResponse,
        SugerenciaItem,
        SyncCatalogoItem,
        SyncCatalogoResponse,
        SyncStatusResponse,
        StockDisponibilidadResponse,
        StockSucursal,
        ProductoStockResumen,
        BusquedaStockResponse,
        PrecioResolucionResponse,
        ListaPrecioCreate,
        ListaPrecioUpdate,
        ListaPrecioResponse,
        PrecioItemCreate,
        PrecioItemResponse,
    )

from backend.shared.database import get_supabase_admin_client
from backend.shared.erp_clients.inventarios import inventarios_client
from backend.shared import stock_ledger
from backend.shared.redis_client import get_stock_cache, set_stock_cache, STOCK_CACHE_TTL_SECONDS
from backend.shared.security import get_current_user, require_jwt_claims

logger = logging.getLogger("maxiconecta.catalogo")
router = APIRouter(prefix="/api/v1/catalogo", tags=["Catálogo"])

STORAGE_BUCKET = "productos"
MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
DATA_URL_PATTERN = re.compile(r"^data:(image/(?:jpeg|png|webp));base64,([A-Za-z0-9+/=]+)$")


# ------------------------------------------------------------------------------
# NORMALIZACIÓN FTS (INSENSIBLE A MAYÚSCULAS Y TILDES / ACCENT-INSENSITIVE)
# ------------------------------------------------------------------------------
def _normalize_text(text: Optional[str]) -> str:
    """Normaliza texto eliminando acentos y tildes, pasando a minúsculas y limpiando espacios."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    cleaned = "".join(c for c in nfkd if not unicodedata.combining(c))
    return cleaned.lower().strip()


# ------------------------------------------------------------------------------
# CATÁLOGO SEMILLA EN MEMORIA (FALLBACK PARA DESARROLLO, PRUEBAS Y ALTA DISPONIBILIDAD)
# ------------------------------------------------------------------------------
_SEED_CATEGORIAS: List[Dict[str, Any]] = [
    {
        "id": UUID("10000000-0000-0000-0000-000000000001"),
        "nombre": "Laptops y PCs",
        "descripcion": "Computadoras portátiles, de escritorio y estaciones de trabajo",
        "padre_id": None,
        "atributos_dinamicos": ["procesador", "ram", "almacenamiento"],
        "activo": True,
    },
    {
        "id": UUID("10000000-0000-0000-0000-000000000002"),
        "nombre": "Periféricos",
        "descripcion": "Teclados, ratones, mousepads y accesorios de entrada",
        "padre_id": None,
        "atributos_dinamicos": ["conexion", "rgb"],
        "activo": True,
    },
    {
        "id": UUID("10000000-0000-0000-0000-000000000003"),
        "nombre": "Monitores",
        "descripcion": "Pantallas gamer, ultrawide y profesionales",
        "padre_id": None,
        "atributos_dinamicos": ["pulgadas", "tasa_refresco", "resolucion"],
        "activo": True,
    },
    {
        "id": UUID("10000000-0000-0000-0000-000000000004"),
        "nombre": "Audio y Video",
        "descripcion": "Auriculares con cancelación de ruido, barras y micrófonos",
        "padre_id": None,
        "atributos_dinamicos": ["inalambrico", "cancelacion_ruido"],
        "activo": True,
    },
    {
        "id": UUID("10000000-0000-0000-0000-000000000005"),
        "nombre": "Cámaras y Fotografía",
        "descripcion": "Cámaras mirrorless, lentes y equipo de transmisión",
        "padre_id": None,
        "atributos_dinamicos": ["sensor", "resolucion_video"],
        "activo": True,
    },
]

_SEED_PRODUCTOS: List[Dict[str, Any]] = [
    {
        "id": UUID("20000000-0000-0000-0000-000000000001"),
        "sku": "LAP-DELL-XPS15",
        "nombre": "Laptop Dell XPS 15 (OLED 4K, i7 13va Gen)",
        "descripcion": "Potente estación de trabajo ultra-ligera con pantalla OLED 3.5K y tarjeta gráfica RTX 4060.",
        "marca": "Dell",
        "categoria_id": UUID("10000000-0000-0000-0000-000000000001"),
        "estado": "publicado",
        "precio": Decimal("8999.00"),
        "stock": 8,
        "imagenes": [
            "https://images.unsplash.com/photo-1593642632823-8f785ba67e45?auto=format&fit=crop&w=600&q=80"
        ],
    },
    {
        "id": UUID("20000000-0000-0000-0000-000000000002"),
        "sku": "LAP-APP-MBP16",
        "nombre": "Apple MacBook Pro 16\" Chip M3 Pro",
        "descripcion": "Rendimiento profesional extremo con CPU de 12 núcleos y pantalla Liquid Retina XDR.",
        "marca": "Apple",
        "categoria_id": UUID("10000000-0000-0000-0000-000000000001"),
        "estado": "publicado",
        "precio": Decimal("18500.00"),
        "stock": 4,
        "imagenes": [
            "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?auto=format&fit=crop&w=600&q=80"
        ],
    },
    {
        "id": UUID("20000000-0000-0000-0000-000000000003"),
        "sku": "MOU-LOG-MX3S",
        "nombre": "Mouse Inalámbrico Logitech MX Master 3S",
        "descripcion": "Sensor óptico 8K DPI silencioso para máxima ergonomía y precisión en múltiples dispositivos.",
        "marca": "Logitech",
        "categoria_id": UUID("10000000-0000-0000-0000-000000000002"),
        "estado": "publicado",
        "precio": Decimal("799.00"),
        "stock": 24,
        "imagenes": [
            "https://images.unsplash.com/photo-1615663245857-ac93bb7c39e7?auto=format&fit=crop&w=600&q=80"
        ],
    },
    {
        "id": UUID("20000000-0000-0000-0000-000000000004"),
        "sku": "TEC-LOG-MXMECH",
        "nombre": "Teclado Mecánico Inalámbrico Logitech MX Mechanical",
        "descripcion": "Interruptores táctiles de bajo perfil con retroiluminación inteligente y conexión Flow.",
        "marca": "Logitech",
        "categoria_id": UUID("10000000-0000-0000-0000-000000000002"),
        "estado": "publicado",
        "precio": Decimal("1150.00"),
        "stock": 15,
        "imagenes": [
            "https://images.unsplash.com/photo-1587829741301-dc798b83add3?auto=format&fit=crop&w=600&q=80"
        ],
    },
    {
        "id": UUID("20000000-0000-0000-0000-000000000005"),
        "sku": "MON-LG-27GP",
        "nombre": "Monitor Gamer LG UltraGear 27\" 165Hz IPS",
        "descripcion": "Panel Nano IPS de 1ms GtG con compatibilidad NVIDIA G-SYNC y resolución QHD.",
        "marca": "LG",
        "categoria_id": UUID("10000000-0000-0000-0000-000000000003"),
        "estado": "publicado",
        "precio": Decimal("2450.00"),
        "stock": 5,
        "imagenes": [
            "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?auto=format&fit=crop&w=600&q=80"
        ],
    },
    {
        "id": UUID("20000000-0000-0000-0000-000000000006"),
        "sku": "MON-SAM-M8",
        "nombre": "Monitor Inteligente Samsung Smart M8 32\" 4K",
        "descripcion": "Centro de entretenimiento y productividad con cámara SlimFit magnética y AirPlay 2.",
        "marca": "Samsung",
        "categoria_id": UUID("10000000-0000-0000-0000-000000000003"),
        "estado": "publicado",
        "precio": Decimal("4200.00"),
        "stock": 7,
        "imagenes": [
            "https://images.unsplash.com/photo-1547119957-637f8679db1e?auto=format&fit=crop&w=600&q=80"
        ],
    },
    {
        "id": UUID("20000000-0000-0000-0000-000000000007"),
        "sku": "AUR-SONY-WH1000",
        "nombre": "Auriculares Sony WH-1000XM5 Noise Cancelling",
        "descripcion": "Líder en cancelación de ruido activa con procesador V1, audio Hi-Res y batería de 30 horas.",
        "marca": "Sony",
        "categoria_id": UUID("10000000-0000-0000-0000-000000000004"),
        "estado": "publicado",
        "precio": Decimal("2890.00"),
        "stock": 12,
        "imagenes": [
            "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=600&q=80"
        ],
    },
    {
        "id": UUID("20000000-0000-0000-0000-000000000008"),
        "sku": "CAM-SONY-A7IV",
        "nombre": "Cámara Digital Sony Alpha 7 IV Full-Frame Mirrorless",
        "descripcion": "Sensor Exmor R de 33 MP, grabación 4K 60p 10-bit y enfoque automático con IA en tiempo real.",
        "marca": "Sony",
        "categoria_id": UUID("10000000-0000-0000-0000-000000000005"),
        "estado": "publicado",
        "precio": Decimal("16999.00"),
        "stock": 3,
        "imagenes": [
            "https://images.unsplash.com/photo-1516035069371-29a1b244cc32?auto=format&fit=crop&w=600&q=80"
        ],
    },
]

# Almacén de catálogo dinámico en memoria
_LOCAL_CATEGORIAS: Dict[UUID, Dict[str, Any]] = {c["id"]: c for c in _SEED_CATEGORIAS}
_LOCAL_PRODUCTOS: Dict[UUID, Dict[str, Any]] = {p["id"]: p for p in _SEED_PRODUCTOS}
_LOCAL_IMAGENES: Dict[UUID, List[Dict[str, Any]]] = {}


def _get_supabase_client_safe() -> Optional[Any]:
    try:
        return get_supabase_admin_client()
    except Exception as e:
        logger.warning(f"Error obteniendo cliente Supabase: {e}")
        return None


def _category_value(value: Any) -> Optional[Dict[str, Any]]:
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _build_product_response(row: Dict[str, Any], cat_dict: Optional[Dict[str, Any]] = None) -> ProductoResponse:
    cat_id = row.get("categoria_id")
    if not cat_dict:
        cat_dict = _LOCAL_CATEGORIAS.get(cat_id)

    cat_obj = None
    if cat_dict:
        cat_obj = CategoriaResponse(
            id=cat_dict["id"],
            nombre=cat_dict["nombre"],
            descripcion=cat_dict.get("descripcion"),
            padre_id=cat_dict.get("padre_id"),
            atributos_dinamicos=cat_dict.get("atributos_dinamicos", []),
            activo=cat_dict.get("activo", True),
        )

    images = row.get("imagenes_producto") or []
    if not images and row.get("imagenes"):
        images = [
            ImagenProductoResponse(
                id=uuid4(),
                url=url,
                nombre=f"{row.get('sku')}-img",
                es_principal=idx == 0,
                orden=idx,
            )
            for idx, url in enumerate(row["imagenes"])
        ]

    variantes = row.get("variantes") or [
        VarianteResponse(
            id=uuid4(),
            producto_id=row["id"],
            sku=f"{row.get('sku')}-BASE",
            nombre_variante="Configuración base",
            atributos={},
            precio=row.get("precio", Decimal("0")),
            precio_costo=Decimal("0"),
        )
    ]

    return ProductoResponse(
        id=row["id"],
        sku=row["sku"],
        nombre=row["nombre"],
        descripcion=row.get("descripcion"),
        marca=row.get("marca"),
        categoria_id=cat_id,
        estado=row.get("estado", "publicado"),
        precio=row.get("precio", Decimal("0")),
        stock=row.get("stock", 10),
        categorias=cat_obj,
        variantes=variantes,
        imagenes_producto=images,
    )


def _product_response_from_db(client: Any, row: Dict[str, Any]) -> ProductoResponse:
    # 1. Si la fila ya trae sus relaciones unificadas mediante JOIN (select("*, categorias(*), variantes(*), imagenes_producto(*)")):
    if "variantes" in row and "categorias" in row:
        try:
            variants = row.get("variantes") or []
            primary_variant = variants[0] if variants else {}
            cat_data = _category_value(row.get("categorias"))
            images = row.get("imagenes_producto") or []
            return ProductoResponse.model_validate(
                {
                    **row,
                    "precio": primary_variant.get("precio", row.get("precio", 0)),
                    "stock": row.get("stock", 10),
                    "categorias": cat_data,
                    "variantes": variants,
                    "imagenes_producto": images,
                }
            )
        except Exception as e:
            logger.warning(f"Aviso al validar fila unificada de DB: {e}")

    # 2. Fallback individual si no vinieron embebidas
    try:
        category_result = client.table("categorias").select("id,nombre,descripcion,padre_id,atributos_dinamicos,activo").eq("id", str(row["categoria_id"])).limit(1).execute()
        variants = client.table("variantes").select("*").eq("producto_id", str(row["id"])).order("created_at").execute().data
        images = client.table("imagenes_producto").select("*").eq("producto_id", str(row["id"])).order("orden").execute().data
        primary_variant = variants[0] if variants else {}
        return ProductoResponse.model_validate(
            {
                **row,
                "precio": primary_variant.get("precio", row.get("precio", 0)),
                "stock": row.get("stock", 10),
                "categorias": _category_value(category_result.data),
                "variantes": variants,
                "imagenes_producto": images,
            }
        )
    except Exception as e:
        logger.warning(f"Error procesando producto desde DB, usando mapeo local: {e}")
        return _build_product_response(row)


def _fetch_all_products(client: Optional[Any] = None, q: Optional[str] = None) -> List[ProductoResponse]:
    """Recupera el universo de productos en una sola consulta relacional (0 problemas N+1) y FTS en PostgreSQL."""
    if client:
        try:
            db_query = client.table("productos").select("*, categorias(*), variantes(*), imagenes_producto(*)").eq("estado", "publicado")
            if q and q.strip():
                try:
                    # Intento de FTS nativo aprovechando el vector search_vector e índice GIN
                    db_query = db_query.text_search("search_vector", q.strip(), options={"type": "plain", "config": "spanish"})
                except Exception:
                    pass
            rows = db_query.execute().data or []
            if rows:
                remote_products = [_product_response_from_db(client, r) for r in rows]
                remote_ids = {str(product.id) for product in remote_products}
                local_fallback = [
                    _build_product_response(product)
                    for product in _LOCAL_PRODUCTOS.values()
                    if str(product["id"]) not in remote_ids
                ]
                return remote_products + local_fallback
        except Exception as e:
            logger.warning(f"Error consultando productos de Supabase: {e}. Usando catálogo local.")

    return [_build_product_response(p) for p in _LOCAL_PRODUCTOS.values()]


def _buscar_producto_por_sku(sku: str) -> Optional[ProductoResponse]:
    for producto in _fetch_all_products(_get_supabase_client_safe()):
        if producto.sku == sku or any(v.sku == sku for v in producto.variantes):
            return producto
    return None


async def _aplicar_stock_disponible(productos: List[ProductoResponse]) -> None:
    """Reemplaza el stock nominal del catálogo por las unidades realmente disponibles."""
    async def actualizar(producto: ProductoResponse) -> None:
        if await stock_ledger.get_base_stock(producto.sku) is None:
            await stock_ledger.register_base_stock(producto.sku, int(producto.stock or 0))
        data = await inventarios_client.consultar_disponibilidad(producto.sku)
        producto.stock = int(data.get("stock_disponible", 0))

    await asyncio.gather(*(actualizar(producto) for producto in productos))


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
    try:
        buckets = client.storage.list_buckets()
        if not any(bucket.name == STORAGE_BUCKET for bucket in buckets):
            client.storage.create_bucket(STORAGE_BUCKET, {"public": True, "file_size_limit": MAX_IMAGE_BYTES})
    except Exception as e:
        logger.warning(f"Aviso al verificar bucket storage: {e}")


# ------------------------------------------------------------------------------
# RF-08: Suscriptores en memoria para el notificador SSE de cambios de catálogo.
# Cada terminal POS conectada mantiene una cola propia; al mutar un producto se
# difunde el evento a todas las colas activas (broadcast simple in-process).
# ------------------------------------------------------------------------------
_SYNC_SUBSCRIBERS: List["asyncio.Queue[Dict[str, Any]]"] = []
_RECENT_SYNC_EVENTS: List[Dict[str, Any]] = []

async def _broadcast_catalogo_event(evento: Dict[str, Any]) -> None:
    evento_completo = {**evento, "emitido_en": datetime.now(timezone.utc).isoformat()}
    _RECENT_SYNC_EVENTS.insert(0, evento_completo)
    if len(_RECENT_SYNC_EVENTS) > 50:
        _RECENT_SYNC_EVENTS.pop()
    for cola in list(_SYNC_SUBSCRIBERS):
        await cola.put(evento_completo)

# ------------------------------------------------------------------------------
# Consulta Rápida de Stock Multi-Sucursal (Modal F3): caché de lectura en
# memoria de muy corta duración para optimizar búsquedas repetidas del mismo
# término mientras el cajero/administrador escribe.
# ------------------------------------------------------------------------------
_STOCK_MULTISUCURSAL_CACHE: Dict[str, Dict[str, Any]] = {}
_STOCK_MULTISUCURSAL_CACHE_TTL = 15  # segundos

# ------------------------------------------------------------------------------
# 1. CATEGORÍAS
# ------------------------------------------------------------------------------
@router.get("/categorias", response_model=List[CategoriaResponse])
async def listar_categorias():
    client = _get_supabase_client_safe()
    if client:
        try:
            result = client.table("categorias").select("id,nombre,descripcion,padre_id,atributos_dinamicos,activo").eq("activo", True).order("nombre").execute()
            if result.data:
                return result.data
        except Exception as e:
            logger.warning(f"Error consultando categorías en Supabase: {e}. Usando datos locales.")

    return [
        CategoriaResponse(
            id=c["id"],
            nombre=c["nombre"],
            descripcion=c.get("descripcion"),
            padre_id=c.get("padre_id"),
            atributos_dinamicos=c.get("atributos_dinamicos", []),
            activo=c.get("activo", True),
        )
        for c in _LOCAL_CATEGORIAS.values()
        if c.get("activo", True)
    ]


@router.post("/categorias", response_model=CategoriaResponse, status_code=status.HTTP_201_CREATED)
async def crear_categoria(payload: CategoriaCreate):
    """RF-02 / US-02: Crear categoría jerárquica con atributos dinámicos."""
    cat_id = uuid4()
    cat_dict = {
        "id": cat_id,
        "nombre": payload.nombre.strip(),
        "descripcion": payload.descripcion.strip() if payload.descripcion else None,
        "padre_id": payload.padre_id,
        "atributos_dinamicos": payload.atributos_dinamicos or [],
        "activo": True
    }

    client = _get_supabase_client_safe()
    if client:
        try:
            insert_payload = {
                "id": str(cat_id),
                "nombre": payload.nombre.strip(),
                "descripcion": payload.descripcion.strip() if payload.descripcion else None,
                "padre_id": str(payload.padre_id) if payload.padre_id else None,
                "atributos_dinamicos": payload.atributos_dinamicos or [],
                "activo": True
            }
            res = client.table("categorias").insert(insert_payload).execute()
            if res.data and len(res.data) > 0:
                created = res.data[0]
                _LOCAL_CATEGORIAS[cat_id] = created
                return CategoriaResponse(**created)
        except Exception as e:
            logger.warning(f"Aviso al insertar categoría en Supabase: {e}. Guardando en memoria local.")

    _LOCAL_CATEGORIAS[cat_id] = cat_dict
    return CategoriaResponse(**cat_dict)


@router.put("/categorias/{id}", response_model=CategoriaResponse)
async def actualizar_categoria(id: UUID, payload: CategoriaUpdate):
    """RF-02 / US-02: Actualizar categoría jerárquica existente."""
    client = _get_supabase_client_safe()
    update_data: Dict[str, Any] = {}
    if payload.nombre is not None:
        update_data["nombre"] = payload.nombre.strip()
    if payload.descripcion is not None:
        update_data["descripcion"] = payload.descripcion.strip()
    if payload.padre_id is not None:
        update_data["padre_id"] = str(payload.padre_id)
    if payload.atributos_dinamicos is not None:
        update_data["atributos_dinamicos"] = payload.atributos_dinamicos
    if payload.activo is not None:
        update_data["activo"] = payload.activo

    if client and update_data:
        try:
            res = client.table("categorias").update(update_data).eq("id", str(id)).execute()
            if res.data and len(res.data) > 0:
                updated = res.data[0]
                _LOCAL_CATEGORIAS[id] = updated
                return CategoriaResponse(**updated)
        except Exception as e:
            logger.warning(f"Error al actualizar categoría en Supabase: {e}")

    if id in _LOCAL_CATEGORIAS:
        current = _LOCAL_CATEGORIAS[id]
        current.update({k: v for k, v in update_data.items() if v is not None})
        return CategoriaResponse(**current)

    raise HTTPException(status_code=404, detail="Categoría no encontrada")


# ------------------------------------------------------------------------------
# 2. MOTOR DE BÚSQUEDA POR TEXTO COMPLETO Y FILTROS FACETADOS (RF-06 / US-06)
# ------------------------------------------------------------------------------
@router.get("/buscar", response_model=BusquedaFacetadaResponse)
@router.get("/productos/buscar", response_model=BusquedaFacetadaResponse)
async def buscar_productos_facetados(
    q: Optional[str] = Query(None, description="Búsqueda Full-Text Search insensible a mayúsculas y tildes"),
    categoria_ids: Optional[str] = Query(None, description="IDs de categorías separados por coma"),
    marcas: Optional[str] = Query(None, description="Nombres de marcas separadas por coma"),
    precio_min: Optional[Decimal] = Query(None, ge=0, description="Precio mínimo en BOB"),
    precio_max: Optional[Decimal] = Query(None, ge=0, description="Precio máximo en BOB"),
    en_stock: Optional[bool] = Query(None, description="Filtrar únicamente productos con stock > 0"),
    ordenar_por: str = Query("relevancia", pattern="^(relevancia|precio_asc|precio_desc|nombre)$"),
    pagina: int = Query(1, ge=1),
    limite: int = Query(20, ge=1, le=100),
):
    """
    Motor central de búsqueda facetada RF-06:
    - Búsqueda Full-Text Search insensible a tildes y mayúsculas.
    - Filtros combinables: categorías múltiples, marcas, rangos de precio y stock.
    - Agregación y recuento dinámico de coincidencias por faceta (counts).
    """
    # 1. Obtener universo de productos (de Supabase mediante JOIN relacional y FTS o fallback local)
    client = _get_supabase_client_safe()
    all_products: List[ProductoResponse] = _fetch_all_products(client, q)

    # Parsear filtros de lista
    cat_filter_set = set(categoria_ids.split(",")) if categoria_ids else set()
    cat_filter_set = {c.strip() for c in cat_filter_set if c.strip()}

    brand_filter_set = {m.strip().lower() for m in marcas.split(",") if m.strip()} if marcas else set()

    normalized_q = _normalize_text(q) if q else ""
    query_tokens = normalized_q.split() if normalized_q else []

    # 2. Filtrado inicial por texto libre FTS (unaccent + case-insensitive)
    text_matched_products: List[ProductoResponse] = []
    for prod in all_products:
        if not query_tokens:
            text_matched_products.append(prod)
            continue

        prod_text = f"{prod.nombre} {prod.sku} {prod.marca or ''} {prod.descripcion or ''}"
        if prod.categorias:
            prod_text += f" {prod.categorias.nombre}"

        normalized_prod_text = _normalize_text(prod_text)
        # Todos los tokens del query deben estar presentes (AND semántico FTS)
        if all(token in normalized_prod_text for token in query_tokens):
            text_matched_products.append(prod)

    # 3. Calcular agregaciones de FACETAS a partir del universo con búsqueda de texto
    # (Permite mostrar al usuario cuántas opciones existen en categorías, marcas, etc.)
    cat_counts: Dict[str, Dict[str, Any]] = {}
    brand_counts: Dict[str, int] = {}
    min_price_found = float("inf")
    max_price_found = 0.0
    stock_count = 0

    for prod in text_matched_products:
        p_price = float(prod.precio)
        if p_price < min_price_found:
            min_price_found = p_price
        if p_price > max_price_found:
            max_price_found = p_price

        if (prod.stock or 0) > 0:
            stock_count += 1

        # Agregación categorías
        if prod.categorias:
            cid = str(prod.categorias.id)
            cname = prod.categorias.nombre
            if cid not in cat_counts:
                cat_counts[cid] = {"id": cid, "etiqueta": cname, "total": 0}
            cat_counts[cid]["total"] += 1

        # Agregación marcas
        if prod.marca:
            bname = prod.marca
            brand_counts[bname] = brand_counts.get(bname, 0) + 1

    if min_price_found == float("inf"):
        min_price_found = 0.0

    facets_categorias = [
        FacetItem(
            id=item["id"],
            etiqueta=item["etiqueta"],
            total=item["total"],
            seleccionado=item["id"] in cat_filter_set,
        )
        for item in cat_counts.values()
    ]
    facets_categorias.sort(key=lambda x: x.etiqueta)

    facets_marcas = [
        FacetItem(
            id=brand,
            etiqueta=brand,
            total=count,
            seleccionado=brand.lower() in brand_filter_set,
        )
        for brand, count in brand_counts.items()
    ]
    facets_marcas.sort(key=lambda x: (-x.total, x.etiqueta))

    # 4. Aplicar filtros facetados acumulativos cruzados
    filtered_items: List[ProductoResponse] = []
    for prod in text_matched_products:
        # Filtro de categoría
        if cat_filter_set:
            if not prod.categorias or str(prod.categorias.id) not in cat_filter_set:
                continue

        # Filtro de marca
        if brand_filter_set:
            if not prod.marca or prod.marca.lower() not in brand_filter_set:
                continue

        # Filtro de precio mínimo
        if precio_min is not None and prod.precio < precio_min:
            continue

        # Filtro de precio máximo
        if precio_max is not None and prod.precio > precio_max:
            continue

        # Filtro de stock
        if en_stock is True and (prod.stock or 0) <= 0:
            continue

        filtered_items.append(prod)

    # 5. Ordenamiento
    if ordenar_por == "precio_asc":
        filtered_items.sort(key=lambda p: p.precio)
    elif ordenar_por == "precio_desc":
        filtered_items.sort(key=lambda p: p.precio, reverse=True)
    elif ordenar_por == "nombre":
        filtered_items.sort(key=lambda p: p.nombre.lower())
    else:
        # Relevancia: si hay query, priorizar los que coinciden en el título
        if normalized_q:
            filtered_items.sort(
                key=lambda p: 0 if normalized_q in _normalize_text(p.nombre) else 1
            )

    # 6. Paginación
    total_coincidencias = len(filtered_items)
    offset = (pagina - 1) * limite
    paginated_items = filtered_items[offset : offset + limite]
    await _aplicar_stock_disponible(paginated_items)

    return BusquedaFacetadaResponse(
        items=paginated_items,
        total_coincidencias=total_coincidencias,
        pagina=pagina,
        limite=limite,
        facetas=FacetasCatalogo(
            categorias=facets_categorias,
            marcas=facets_marcas,
            precio=RangoPrecioFacet(min=round(min_price_found, 2), max=round(max_price_found, 2)),
            en_stock=stock_count,
            total_general=len(all_products),
        ),
    )


# ------------------------------------------------------------------------------
# 3. AUTOCOMPLETADO PREDICTIVO (TYPEAHEAD SUGGESTIONS RF-06 / US-06)
# ------------------------------------------------------------------------------
@router.get("/sugerencias", response_model=List[SugerenciaItem])
@router.get("/productos/sugerencias", response_model=List[SugerenciaItem])
async def obtener_sugerencias(
    q: str = Query(..., min_length=1, description="Prefijo o término de búsqueda para sugerencias rápidas"),
    limite: int = Query(5, ge=1, le=10),
):
    """Devuelve sugerencias instantáneas para el menú desplegable predictivo del buscador."""
    norm_q = _normalize_text(q)
    if not norm_q:
        return []

    client = _get_supabase_client_safe()
    all_products: List[ProductoResponse] = _fetch_all_products(client, q)

    sugerencias: List[SugerenciaItem] = []
    for prod in all_products:
        prod_title_norm = _normalize_text(prod.nombre)
        prod_sku_norm = _normalize_text(prod.sku)
        prod_brand_norm = _normalize_text(prod.marca or "")

        if norm_q in prod_title_norm or norm_q in prod_sku_norm or norm_q in prod_brand_norm:
            first_img = prod.imagenes_producto[0].url if prod.imagenes_producto else None
            cat_name = prod.categorias.nombre if prod.categorias else "General"
            sugerencias.append(
                SugerenciaItem(
                    id=prod.id,
                    nombre=prod.nombre,
                    sku=prod.sku,
                    categoria=cat_name,
                    marca=prod.marca,
                    precio=prod.precio,
                    imagen_url=first_img,
                    stock=prod.stock,
                )
            )
            if len(sugerencias) >= limite:
                break

    return sugerencias


# ------------------------------------------------------------------------------
# 4. MOTOR DE RECOMENDACIONES Y VENTA CRUZADA (CROSS-SELLING RF-19 / US-19)
# ------------------------------------------------------------------------------
@router.get("/recomendaciones", response_model=List[ProductoResponse])
@router.get("/productos/{id}/recomendados", response_model=List[ProductoResponse])
async def obtener_productos_recomendados(
    id: Optional[UUID] = None,
    categoria_id: Optional[UUID] = None,
    limite: int = Query(4, ge=1, le=12, description="Número de recomendaciones a retornar"),
):
    """
    RF-19: Motor algorítmico de recomendaciones y venta cruzada (Cross-selling / Up-selling):
    - Si se especifica producto o categoría, prioriza ítems afines o complementarios.
    - Si una búsqueda dio 0 resultados o no se envía ID, recomienda los artículos mejor calificados y de mayor disponibilidad.
    """
    client = _get_supabase_client_safe()
    all_products = _fetch_all_products(client)

    if not all_products:
        return []

    target_prod = None
    if id:
        target_prod = next((p for p in all_products if p.id == id), None)

    cat_target_id = categoria_id or (target_prod.categoria_id if target_prod else None)
    recomendados: List[ProductoResponse] = []

    # 1. Si tenemos categoría objetivo: filtrar por la misma categoría (excluyendo el ítem actual)
    if cat_target_id:
        misma_cat = [
            p for p in all_products 
            if p.categoria_id == cat_target_id and (not target_prod or p.id != target_prod.id)
        ]
        misma_cat.sort(key=lambda p: (-(p.stock or 0), p.precio))
        recomendados.extend(misma_cat[:limite])

    # 2. Si aún faltan productos para completar el límite: rellenar con artículos destacados y con stock
    if len(recomendados) < limite:
        resto = [
            p for p in all_products 
            if p not in recomendados and (not target_prod or p.id != target_prod.id)
        ]
        resto.sort(key=lambda p: (0 if (p.stock or 0) > 0 else 1, -(p.stock or 0)))
        recomendados.extend(resto[: limite - len(recomendados)])

    recomendados = recomendados[:limite]
    await _aplicar_stock_disponible(recomendados)
    return recomendados


# ------------------------------------------------------------------------------
# 5. LISTADO ESTÁNDAR Y DETALLE DE PRODUCTOS (COMPATIBILIDAD HACIA ATRÁS)
# ------------------------------------------------------------------------------
@router.get("/productos", response_model=List[ProductoResponse])
async def listar_productos(
    q: Optional[str] = Query(None, description="Texto de búsqueda facetada"),
    categoria_id: Optional[UUID] = Query(None),
    estado: Optional[str] = Query(None, description="Filtrar por estado del ciclo de vida"),
    precio_min: Optional[Decimal] = Query(None),
    precio_max: Optional[Decimal] = Query(None),
):
    client = _get_supabase_client_safe()
    if client:
        try:
            query = client.table("productos").select("*, categorias(*), variantes(*), imagenes_producto(*)")
            if estado:
                query = query.eq("estado", estado)
            if q:
                query = query.or_(f"nombre.ilike.%{q}%,sku.ilike.%{q}%,marca.ilike.%{q}%")
            if categoria_id:
                query = query.eq("categoria_id", str(categoria_id))
            result = query.order("created_at", desc=True).execute()
            if result.data:
                products = [_product_response_from_db(client, row) for row in result.data]
                if precio_min is not None:
                    products = [product for product in products if product.precio >= precio_min]
                if precio_max is not None:
                    products = [product for product in products if product.precio <= precio_max]
                return products
        except Exception as e:
            logger.warning(f"Error en listar_productos de Supabase: {e}. Usando fallback local.")

    # Fallback local en memoria
    norm_q = _normalize_text(q) if q else None
    results = []
    for p in _LOCAL_PRODUCTOS.values():
        prod_obj = _build_product_response(p)
        if norm_q:
            combined = f"{p['nombre']} {p['sku']} {p.get('marca', '')}"
            if norm_q not in _normalize_text(combined):
                continue
        if categoria_id and p.get("categoria_id") != categoria_id:
            continue
        if precio_min is not None and prod_obj.precio < precio_min:
            continue
        if precio_max is not None and prod_obj.precio > precio_max:
            continue
        results.append(prod_obj)

    return results


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

    client = _get_supabase_client_safe()
    universo = _fetch_all_products(client)
    coincidencias = [
        p for p in universo
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


@router.get("/productos/{product_id}", response_model=ProductoResponse)
async def obtener_producto(product_id: UUID):
    client = _get_supabase_client_safe()
    if client:
        try:
            result = client.table("productos").select("*").eq("id", str(product_id)).single().execute()
            if result.data:
                return _product_response_from_db(client, result.data)
        except Exception:
            pass

    if product_id in _LOCAL_PRODUCTOS:
        return _build_product_response(_LOCAL_PRODUCTOS[product_id])

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")


@router.post("/productos", response_model=ProductoResponse, status_code=status.HTTP_201_CREATED)
@require_jwt_claims("sub", allowed_roles={"administrador", "gerente_comercial"})
async def crear_producto(
    payload: ProductoCreate,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    client = _get_supabase_client_safe()
    new_id = uuid4()
    if not client:
        # Guardar en memoria local
        new_prod = {
            "id": new_id,
            "sku": payload.sku.upper(),
            "nombre": payload.nombre,
            "descripcion": payload.descripcion,
            "marca": payload.marca,
            "categoria_id": payload.categoria_id,
            "estado": "publicado",
            "precio": payload.precio,
            "stock": 10,
            "imagenes": [img.data_url for img in payload.imagenes if not img.data_url.startswith("data:")] or [
                "https://images.unsplash.com/photo-1526738549149-8e07eca6c147?auto=format&fit=crop&w=600&q=80"
            ],
        }
        _LOCAL_PRODUCTOS[new_id] = new_prod
        return _build_product_response(new_prod)

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
    res = _product_response_from_db(client, created.data)
    await _broadcast_catalogo_event({
        "tipo": "producto_creado",
        "producto_id": str(res.id),
        "sku": res.sku,
        "nombre": res.nombre,
        "precio": float(res.precio) if res.precio else None,
        "estado": res.estado,
        "updated_at": res.updated_at.isoformat(),
    })
    return res

@router.patch("/productos/{id}", response_model=ProductoResponse)
async def actualizar_producto(id: UUID, payload: ProductoUpdate):
    """
    RF-08: Actualiza datos/precio de un producto y dispara el evento de
    sincronización multicanal (notificador SSE) hacia las terminales POS
    conectadas, para mantener consistencia de datos y precios entre canales.
    """
    client = _get_supabase_client_safe()
    if client:
        update_data = {}
        if payload.nombre is not None:
            update_data["nombre"] = payload.nombre
        if payload.descripcion is not None:
            update_data["descripcion"] = payload.descripcion
        if payload.marca is not None:
            update_data["marca"] = payload.marca
        if payload.estado is not None:
            update_data["estado"] = payload.estado
        if payload.categoria_id is not None:
            update_data["categoria_id"] = str(payload.categoria_id)

        if update_data:
            client.table("productos").update(update_data).eq("id", str(id)).execute()

        if payload.precio is not None or payload.atributos is not None:
            var_row = client.table("variantes").select("id, atributos").eq("producto_id", str(id)).order("created_at").limit(1).execute()
            if var_row.data:
                var_update = {}
                if payload.precio is not None:
                    var_update["precio"] = float(payload.precio)
                if payload.atributos is not None:
                    var_update["atributos"] = payload.atributos
                if var_update:
                    client.table("variantes").update(var_update).eq("id", var_row.data[0]["id"]).execute()

        prod_res = client.table("productos").select("*, categorias(*), variantes(*), imagenes_producto(*)").eq("id", str(id)).limit(1).execute()
        if prod_res.data:
            resp = _product_response_from_db(client, prod_res.data[0])
            await _broadcast_catalogo_event({
                "tipo": "producto_actualizado",
                "producto_id": str(resp.id),
                "sku": resp.sku,
                "nombre": resp.nombre,
                "precio": float(resp.precio) if resp.precio else None,
                "estado": resp.estado,
                "updated_at": resp.updated_at.isoformat(),
            })
            return resp

    if id in _LOCAL_PRODUCTOS:
        p = _LOCAL_PRODUCTOS[id]
        if payload.nombre is not None:
            p["nombre"] = payload.nombre
        if payload.descripcion is not None:
            p["descripcion"] = payload.descripcion
        if payload.marca is not None:
            p["marca"] = payload.marca
        if payload.estado is not None:
            p["estado"] = payload.estado
        if payload.categoria_id is not None:
            p["categoria_id"] = payload.categoria_id
        if payload.precio is not None:
            p["precio"] = payload.precio
        if payload.atributos is not None and "variantes" in p and len(p["variantes"]) > 0:
            p["variantes"][0]["atributos"] = payload.atributos

        resp = _build_product_response(p)
        await _broadcast_catalogo_event({
            "tipo": "producto_actualizado",
            "producto_id": str(resp.id),
            "sku": resp.sku,
            "nombre": resp.nombre,
            "precio": float(resp.precio) if resp.precio else None,
            "estado": resp.estado,
            "updated_at": resp.updated_at.isoformat(),
        })
        return resp

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")


@router.put("/productos/{id}", response_model=ProductoResponse)
async def actualizar_producto_completo(id: UUID, payload: ProductoUpdate):
    """Alias PUT para actualizar producto completo o parcial."""
    return await actualizar_producto(id, payload)


@router.delete("/productos/{id}", status_code=status.HTTP_200_OK)
async def eliminar_producto(id: UUID):
    """
    Elimina un producto del catálogo y difunde el evento SSE multicanal.
    """
    client = _get_supabase_client_safe()
    if client:
        client.table("productos").delete().eq("id", str(id)).execute()
        await _broadcast_catalogo_event({
            "tipo": "producto_eliminado",
            "producto_id": str(id),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        return {"mensaje": f"Producto {id} eliminado exitosamente", "id": str(id)}

    if id in _LOCAL_PRODUCTOS:
        _LOCAL_PRODUCTOS.pop(id, None)
        await _broadcast_catalogo_event({
            "tipo": "producto_eliminado",
            "producto_id": str(id),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        return {"mensaje": f"Producto {id} eliminado exitosamente", "id": str(id)}

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")


# ==============================================================================
# GESTIÓN MULTIMEDIA E IMÁGENES DE PRODUCTOS (KAN-75 / KAN-76 / KAN-77 / KAN-78)
# ==============================================================================

@router.get("/productos/{id}/imagenes")
async def listar_imagenes_producto(id: UUID):
    """
    Lista las imágenes de un producto ordenadas por orden y created_at.
    Soporta Supabase PostgreSQL y fallback en memoria.
    """
    client = _get_supabase_client_safe()
    if client:
        try:
            prod_check = client.table("productos").select("id").eq("id", str(id)).execute()
            if prod_check.data:
                res = (
                    client.table("imagenes_producto")
                    .select("*")
                    .eq("producto_id", str(id))
                    .order("orden")
                    .order("created_at")
                    .execute()
                )
                raw_list = res.data or []
                enriched = []
                for img in raw_list:
                    url = img.get("url") or ""
                    thumb = url
                    marker = f"/object/public/{STORAGE_BUCKET}/{id}/"
                    if marker in url:
                        thumb = url.replace(f"/{id}/", f"/{id}/thumbs/")
                    enriched.append({
                        **img,
                        "thumbnailUrl": thumb,
                    })
                return {"imagenes": enriched}
        except Exception as e:
            logger.warning(f"Error consultando imagenes_producto de Supabase para {id}: {e}")

    # Fallback local en memoria
    if id in _LOCAL_IMAGENES:
        return {"imagenes": _LOCAL_IMAGENES[id]}

    if id in _LOCAL_PRODUCTOS:
        p = _LOCAL_PRODUCTOS[id]
        img_urls = p.get("imagenes") or []
        local_list = [
            {
                "id": str(uuid4()),
                "producto_id": str(id),
                "variante_id": None,
                "url": u,
                "thumbnailUrl": u,
                "es_principal": idx == 0,
                "orden": idx,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            for idx, u in enumerate(img_urls)
        ]
        _LOCAL_IMAGENES[id] = local_list
        return {"imagenes": local_list}

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")


@router.post("/productos/{id}/imagenes", status_code=status.HTTP_201_CREATED)
async def subir_imagenes_producto(
    id: UUID,
    imagenes: List[UploadFile] = File(...),
):
    """
    Sube una o múltiples imágenes para un producto (multipart/form-data).
    Guarda en Supabase Storage bucket 'productos' e inserta metadatos en imagenes_producto.
    """
    if not imagenes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se enviaron archivos de imagen."
        )

    client = _get_supabase_client_safe()
    uploaded_results = []

    if client:
        try:
            prod_check = client.table("productos").select("id, nombre").eq("id", str(id)).execute()
            if not prod_check.data:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado.")

            existing_res = (
                client.table("imagenes_producto")
                .select("id, es_principal, orden")
                .eq("producto_id", str(id))
                .order("orden", desc=True)
                .execute()
            )
            existing_images = existing_res.data or []
            current_max_order = max([i.get("orden", 0) for i in existing_images], default=-1)
            has_principal = any(i.get("es_principal") for i in existing_images)

            _ensure_bucket(client)

            for idx, file in enumerate(imagenes):
                content = await file.read()
                if not content:
                    continue
                if len(content) > MAX_IMAGE_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"La imagen {file.filename} excede el límite de 5 MB."
                    )

                content_type = file.content_type or "image/jpeg"
                extension = ALLOWED_IMAGE_TYPES.get(content_type, "jpg")
                file_uid = uuid4()
                path = f"productos/{id}/{file_uid}.{extension}"

                client.storage.from_(STORAGE_BUCKET).upload(
                    path,
                    content,
                    {"content-type": content_type, "upsert": "true"}
                )
                image_url = client.storage.from_(STORAGE_BUCKET).get_public_url(path)

                current_max_order += 1
                is_principal = not has_principal and idx == 0
                if is_principal:
                    has_principal = True

                insert_payload = {
                    "id": str(file_uid),
                    "producto_id": str(id),
                    "url": image_url,
                    "es_principal": is_principal,
                    "orden": current_max_order,
                }
                insert_res = client.table("imagenes_producto").insert(insert_payload).execute()
                record = insert_res.data[0] if insert_res.data else insert_payload
                record["thumbnailUrl"] = image_url
                uploaded_results.append(record)

            await _broadcast_catalogo_event({
                "tipo": "producto_imagenes_actualizadas",
                "producto_id": str(id),
                "total_imagenes": len(existing_images) + len(uploaded_results),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })

            return {
                "success": True,
                "message": f"{len(uploaded_results)} recurso(s) multimedia procesado(s) exitosamente.",
                "imagenes": uploaded_results,
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error subiendo imágenes a Supabase: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    # Fallback local en memoria
    if id not in _LOCAL_PRODUCTOS and id not in _LOCAL_IMAGENES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado.")

    if id not in _LOCAL_IMAGENES:
        _LOCAL_IMAGENES[id] = []

    has_principal = any(i.get("es_principal") for i in _LOCAL_IMAGENES[id])
    current_max_order = max([i.get("orden", 0) for i in _LOCAL_IMAGENES[id]], default=-1)

    for idx, file in enumerate(imagenes):
        content = await file.read()
        if not content:
            continue
        file_uid = uuid4()
        b64 = base64.b64encode(content).decode("utf-8")
        data_url = f"data:{file.content_type or 'image/jpeg'};base64,{b64}"
        current_max_order += 1
        is_principal = not has_principal and idx == 0
        if is_principal:
            has_principal = True

        rec = {
            "id": str(file_uid),
            "producto_id": str(id),
            "variante_id": None,
            "url": data_url,
            "thumbnailUrl": data_url,
            "es_principal": is_principal,
            "orden": current_max_order,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        _LOCAL_IMAGENES[id].append(rec)
        uploaded_results.append(rec)

    return {
        "success": True,
        "message": f"{len(uploaded_results)} recurso(s) multimedia guardado(s) exitosamente.",
        "imagenes": uploaded_results,
    }


@router.patch("/productos/{id}/imagenes/{imagen_id}/principal")
async def marcar_imagen_principal(id: UUID, imagen_id: UUID):
    """
    Designa una imagen como portada principal del producto y desmarca las demás.
    """
    client = _get_supabase_client_safe()
    if client:
        try:
            client.table("imagenes_producto").update({"es_principal": False}).eq("producto_id", str(id)).execute()
            res = (
                client.table("imagenes_producto")
                .update({"es_principal": True})
                .eq("id", str(imagen_id))
                .eq("producto_id", str(id))
                .execute()
            )
            if not res.data:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Imagen no encontrada para este producto.")

            updated = res.data[0]
            await _broadcast_catalogo_event({
                "tipo": "producto_portada_actualizada",
                "producto_id": str(id),
                "imagen_id": str(imagen_id),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            return {
                "success": True,
                "message": "Imagen designada como portada principal del producto.",
                "imagen": updated,
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error marcando imagen principal en Supabase: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    # Fallback local
    if id in _LOCAL_IMAGENES:
        found = False
        target_img = None
        for img in _LOCAL_IMAGENES[id]:
            is_match = (str(img["id"]) == str(imagen_id))
            img["es_principal"] = is_match
            if is_match:
                found = True
                target_img = img
        if not found:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Imagen no encontrada para este producto.")
        return {
            "success": True,
            "message": "Imagen designada como portada principal del producto.",
            "imagen": target_img,
        }

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado.")


@router.delete("/productos/{id}/imagenes/{imagen_id}")
async def eliminar_imagen_producto(id: UUID, imagen_id: UUID):
    """
    Elimina un recurso multimedia de la base de datos y de Supabase Storage.
    Si era la imagen principal, promueve automáticamente la siguiente en orden.
    """
    client = _get_supabase_client_safe()
    if client:
        try:
            find_res = client.table("imagenes_producto").select("*").eq("id", str(imagen_id)).eq("producto_id", str(id)).execute()
            if not find_res.data:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurso multimedia no encontrado.")

            img_record = find_res.data[0]
            url = img_record.get("url") or ""

            marker = f"/storage/v1/object/public/{STORAGE_BUCKET}/"
            if marker in url:
                try:
                    rel_path = url.split(marker)[1]
                    client.storage.from_(STORAGE_BUCKET).remove([rel_path])
                except Exception as st_err:
                    logger.warning(f"Aviso al eliminar archivo de storage: {st_err}")

            client.table("imagenes_producto").delete().eq("id", str(imagen_id)).eq("producto_id", str(id)).execute()

            if img_record.get("es_principal"):
                remaining = client.table("imagenes_producto").select("id").eq("producto_id", str(id)).order("orden").limit(1).execute()
                if remaining.data:
                    client.table("imagenes_producto").update({"es_principal": True}).eq("id", remaining.data[0]["id"]).execute()

            await _broadcast_catalogo_event({
                "tipo": "producto_imagen_eliminada",
                "producto_id": str(id),
                "imagen_id": str(imagen_id),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })

            return {
                "success": True,
                "message": "Recurso multimedia eliminado exitosamente.",
                "id": str(imagen_id),
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error eliminando imagen en Supabase: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    # Fallback local
    if id in _LOCAL_IMAGENES:
        initial_len = len(_LOCAL_IMAGENES[id])
        _LOCAL_IMAGENES[id] = [i for i in _LOCAL_IMAGENES[id] if str(i["id"]) != str(imagen_id)]
        if len(_LOCAL_IMAGENES[id]) == initial_len:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurso multimedia no encontrado.")
        if _LOCAL_IMAGENES[id] and not any(i.get("es_principal") for i in _LOCAL_IMAGENES[id]):
            _LOCAL_IMAGENES[id][0]["es_principal"] = True
        return {
            "success": True,
            "message": "Recurso multimedia eliminado exitosamente.",
            "id": str(imagen_id),
        }

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado.")


@router.put("/productos/{id}/imagenes/reordenar")
async def reordenar_imagenes_producto(id: UUID, payload: Dict[str, Any]):
    """
    Reordena la galería visual de imágenes de un producto.
    """
    ordenes = payload.get("ordenes")
    if not isinstance(ordenes, list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='El cuerpo debe contener un arreglo "ordenes" con { id, orden }.'
        )

    client = _get_supabase_client_safe()
    if client:
        try:
            for item in ordenes:
                item_id = item.get("id")
                item_orden = item.get("orden", 0)
                if item_id:
                    client.table("imagenes_producto").update({"orden": item_orden}).eq("id", str(item_id)).eq("producto_id", str(id)).execute()

            updated_list_res = client.table("imagenes_producto").select("*").eq("producto_id", str(id)).order("orden").execute()
            return {
                "success": True,
                "message": "Orden de galería actualizado exitosamente.",
                "imagenes": updated_list_res.data or [],
            }
        except Exception as e:
            logger.error(f"Error reordenando imágenes en Supabase: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    # Fallback local
    if id in _LOCAL_IMAGENES:
        orden_map = {str(item.get("id")): item.get("orden", 0) for item in ordenes}
        for img in _LOCAL_IMAGENES[id]:
            if str(img["id"]) in orden_map:
                img["orden"] = orden_map[str(img["id"])]
        _LOCAL_IMAGENES[id].sort(key=lambda x: x.get("orden", 0))
        return {
            "success": True,
            "message": "Orden de galería actualizado exitosamente.",
            "imagenes": _LOCAL_IMAGENES[id],
        }

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado.")



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
    client = _get_supabase_client_safe()
    universo = _fetch_all_products(client)
    candidatos = sorted(universo, key=lambda p: p.updated_at)

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
            precio_referencia=p.precio or Decimal("0"),
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


@router.get("/sync-status", response_model=SyncStatusResponse)
async def get_sync_status():
    """
    RF-08: Estado y métricas de sincronización multicanal (Web <-> POS)
    para el Administrador o Sistema.
    """
    client = _get_supabase_client_safe()
    universo = _fetch_all_products(client)
    max_updated = max((p.updated_at for p in universo), default=None) if universo else None

    return SyncStatusResponse(
        suscriptores_activos=len(_SYNC_SUBSCRIBERS),
        total_productos=len(universo),
        ultima_sincronizacion=max_updated,
        eventos_recientes=_RECENT_SYNC_EVENTS[:20],
        estado="operativo"
    )


@router.post("/sync-catalogo/forzar")
async def forzar_sincronizacion_catalogo():
    """
    RF-08: Fuerza una difusión masiva de sincronización a todas las terminales
    POS conectadas mediante SSE, solicitando actualización inmediata de catálogo.
    """
    client = _get_supabase_client_safe()
    universo = _fetch_all_products(client)
    now_iso = datetime.now(timezone.utc).isoformat()

    evento = {
        "tipo": "sincronizacion_masiva",
        "mensaje": "Sincronización forzada por Administrador o Sistema",
        "total_productos": len(universo),
        "origen": "administrador",
        "emitido_en": now_iso
    }
    await _broadcast_catalogo_event(evento)

    return {
        "mensaje": "Evento de sincronización masiva emitido exitosamente a todas las terminales POS.",
        "suscriptores_notificados": len(_SYNC_SUBSCRIBERS),
        "total_productos": len(universo),
        "timestamp": now_iso
    }


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

    if await stock_ledger.get_base_stock(sku) is None:
        producto = _buscar_producto_por_sku(sku)
        if producto:
            await stock_ledger.register_base_stock(sku, int(producto.stock or 0))

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
# RF-04 / US-04: LISTAS DE PRECIOS DIFERENCIADAS (CANAL, SUCURSAL, TIPO CLIENTE)
# ==============================================================================

_SUCURSALES_NOMBRES_MAP = {
    "SUC-LP-CENTRAL": "Sucursal Central - La Paz",
    "SUC-LP-SOPOCACHI": "Sucursal Sopocachi - La Paz",
    "SUC-SCZ-EQUIPETROL": "Sucursal Equipetrol - Santa Cruz",
    "SUC-CBB-CENTRO": "Sucursal Centro - Cochabamba"
}

# listas_precios.sucursal_id es UUID en Supabase: los códigos de sucursal se guardan como UUID deterministas.
_SUCURSAL_NAMESPACE = UUID("5b0f7c3e-2d4a-4c8e-9f1b-7a6d3e2c1b90")
_SUCURSAL_UUIDS = {codigo: str(uuid5(_SUCURSAL_NAMESPACE, codigo)) for codigo in _SUCURSALES_NOMBRES_MAP}
_SUCURSAL_CODIGOS = {valor: codigo for codigo, valor in _SUCURSAL_UUIDS.items()}


def _sucursal_a_db(sucursal_id: Optional[str]) -> Optional[str]:
    if not sucursal_id:
        return None
    if sucursal_id in _SUCURSAL_UUIDS:
        return _SUCURSAL_UUIDS[sucursal_id]
    try:
        return str(UUID(str(sucursal_id)))
    except ValueError:
        return None


def _sucursal_desde_db(valor: Any) -> Optional[str]:
    if not valor:
        return None
    return _SUCURSAL_CODIGOS.get(str(valor), str(valor))


def _nombre_sucursal(codigo: Optional[str]) -> str:
    if not codigo:
        return "General / Multicanal"
    return _SUCURSALES_NOMBRES_MAP.get(codigo, "Sucursal Específica")


def _obtener_listas_precios(supabase: Optional[Any]) -> List[Dict[str, Any]]:
    """Listas persistidas en Supabase más las listas semilla que aún no se han persistido."""
    listas: Dict[str, Dict[str, Any]] = {}
    if supabase:
        try:
            for row in supabase.table("listas_precios").select("*").execute().data or []:
                codigo = _sucursal_desde_db(row.get("sucursal_id"))
                listas[str(row["id"])] = {
                    **row,
                    "id": str(row["id"]),
                    "sucursal_id": codigo,
                    "sucursal_nombre": _nombre_sucursal(codigo),
                    "moneda": row.get("moneda") or "BOB",
                    "activo": bool(row.get("activo", True)),
                }
        except Exception as e:
            logger.warning(f"Error consultando listas_precios en Supabase: {e}")
    for lista in _LOCAL_LISTAS_PRECIOS.values():
        listas.setdefault(str(lista["id"]), {**lista, "id": str(lista["id"])})
    return list(listas.values())


def _obtener_items_precios(supabase: Optional[Any], lista_id: Optional[str] = None) -> List[Dict[str, Any]]:
    items: Dict[tuple, Dict[str, Any]] = {}
    if supabase:
        try:
            query = supabase.table("precios_items").select("id, lista_precio_id, variante_id, precio, fecha_inicio, fecha_fin")
            if lista_id:
                query = query.eq("lista_precio_id", lista_id)
            for row in query.execute().data or []:
                clave = (str(row["lista_precio_id"]), str(row["variante_id"]))
                items[clave] = {**row, "id": str(row["id"]), "lista_precio_id": clave[0], "variante_id": clave[1]}
        except Exception as e:
            logger.warning(f"Error consultando precios_items en Supabase: {e}")
    for item in _LOCAL_PRECIOS_ITEMS.values():
        clave = (str(item["lista_precio_id"]), str(item["variante_id"]))
        if lista_id and clave[0] != lista_id:
            continue
        items.setdefault(clave, {**item, "lista_precio_id": clave[0], "variante_id": clave[1]})
    return list(items.values())


def _buscar_producto_por_id(universo: List[ProductoResponse], identificador: str) -> Optional[ProductoResponse]:
    for producto in universo:
        if str(producto.id) == identificador or any(str(v.id) == identificador for v in producto.variantes):
            return producto
    return None


def _es_producto_local(producto: ProductoResponse) -> bool:
    return str(producto.id) in {str(clave) for clave in _LOCAL_PRODUCTOS}


def _lista_precio_response(lista: Dict[str, Any], total_items: int = 0) -> ListaPrecioResponse:
    return ListaPrecioResponse(
        id=str(lista["id"]),
        nombre=lista["nombre"],
        canal=lista["canal"],
        tipo_cliente=lista["tipo_cliente"],
        sucursal_id=lista.get("sucursal_id"),
        sucursal_nombre=lista.get("sucursal_nombre") or _nombre_sucursal(lista.get("sucursal_id")),
        moneda=lista.get("moneda") or "BOB",
        activo=bool(lista.get("activo", True)),
        total_items=total_items,
        items=[],
        created_at=lista.get("created_at"),
    )

_LOCAL_LISTAS_PRECIOS: Dict[str, Dict[str, Any]] = {
    "11111111-1111-1111-1111-111111111111": {
        "id": "11111111-1111-1111-1111-111111111111",
        "nombre": "Lista Estándar Web (Retail)",
        "canal": "web",
        "tipo_cliente": "retail",
        "sucursal_id": None,
        "sucursal_nombre": "Canal Digital / Nacional",
        "moneda": "BOB",
        "activo": True,
        "created_at": datetime.now(timezone.utc),
    },
    "22222222-2222-2222-2222-222222222222": {
        "id": "22222222-2222-2222-2222-222222222222",
        "nombre": "Lista Sucursal Central POS (Retail)",
        "canal": "pos",
        "tipo_cliente": "retail",
        "sucursal_id": "SUC-LP-CENTRAL",
        "sucursal_nombre": "Sucursal Central - La Paz",
        "moneda": "BOB",
        "activo": True,
        "created_at": datetime.now(timezone.utc),
    },
    "33333333-3333-3333-3333-333333333333": {
        "id": "33333333-3333-3333-3333-333333333333",
        "nombre": "Lista B2B Mayorista Corporativo",
        "canal": "b2b",
        "tipo_cliente": "corporativo_b2b",
        "sucursal_id": None,
        "sucursal_nombre": "Canal Mayorista B2B",
        "moneda": "BOB",
        "activo": True,
        "created_at": datetime.now(timezone.utc),
    },
    "44444444-4444-4444-4444-444444444444": {
        "id": "44444444-4444-4444-4444-444444444444",
        "nombre": "Lista Dólares Corporativo (USD)",
        "canal": "web",
        "tipo_cliente": "corporativo_b2b",
        "sucursal_id": None,
        "sucursal_nombre": "Comercio Exterior / Corporativo",
        "moneda": "USD",
        "activo": True,
        "created_at": datetime.now(timezone.utc),
    }
}

_LOCAL_PRECIOS_ITEMS: Dict[str, Dict[str, Any]] = {
    "item-b2b-01": {
        "id": "55555555-5555-5555-5555-555555555551",
        "lista_precio_id": "33333333-3333-3333-3333-333333333333",
        "variante_id": "20000000-0000-0000-0000-000000000001",
        "sku": "LAP-DELL-XPS15",
        "nombre": "Laptop Dell XPS 15 (OLED 4K, i7 13va Gen)",
        "precio": Decimal("7649.00"),
        "fecha_inicio": datetime.now(timezone.utc),
        "fecha_fin": None,
    },
    "item-usd-01": {
        "id": "55555555-5555-5555-5555-555555555552",
        "lista_precio_id": "44444444-4444-4444-4444-444444444444",
        "variante_id": "20000000-0000-0000-0000-000000000001",
        "sku": "LAP-DELL-XPS15",
        "nombre": "Laptop Dell XPS 15 (OLED 4K, i7 13va Gen)",
        "precio": Decimal("1100.00"),
        "fecha_inicio": datetime.now(timezone.utc),
        "fecha_fin": None,
    },
    "item-pos-01": {
        "id": "55555555-5555-5555-5555-555555555553",
        "lista_precio_id": "22222222-2222-2222-2222-222222222222",
        "variante_id": "20000000-0000-0000-0000-000000000001",
        "sku": "LAP-DELL-XPS15",
        "nombre": "Laptop Dell XPS 15 (OLED 4K, i7 13va Gen)",
        "precio": Decimal("8799.00"),
        "fecha_inicio": datetime.now(timezone.utc),
        "fecha_fin": None,
    }
}

@router.get("/listas-precios", response_model=List[ListaPrecioResponse])
async def listar_listas_precios(
    canal: Optional[str] = Query(None, pattern="^(web|pos|b2b)$"),
    tipo_cliente: Optional[str] = Query(None, pattern="^(retail|corporativo_b2b)$"),
    sucursal_id: Optional[str] = None,
    activo: Optional[bool] = None,
):
    """
    RF-04: Lista las listas de precios diferenciadas configuradas en el sistema.
    """
    supabase = _get_supabase_client_safe()
    conteo: Dict[str, int] = {}
    for item in _obtener_items_precios(supabase):
        conteo[item["lista_precio_id"]] = conteo.get(item["lista_precio_id"], 0) + 1

    resultado = []
    for lista in _obtener_listas_precios(supabase):
        if canal and lista["canal"] != canal:
            continue
        if tipo_cliente and lista["tipo_cliente"] != tipo_cliente:
            continue
        if sucursal_id and lista.get("sucursal_id") != sucursal_id:
            continue
        if activo is not None and bool(lista.get("activo", True)) != activo:
            continue
        resultado.append(_lista_precio_response(lista, conteo.get(lista["id"], 0)))
    resultado.sort(key=lambda lista: lista.nombre)
    return resultado

@router.post("/listas-precios", response_model=ListaPrecioResponse, status_code=status.HTTP_201_CREATED)
@require_jwt_claims("sub", allowed_roles={"administrador", "gerente_comercial"})
async def crear_lista_precio(
    payload: ListaPrecioCreate,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    RF-04: Crea una nueva lista de precios diferenciada (Administrador / Gerente Comercial).
    """
    new_id = str(uuid4())
    suc_nombre = payload.sucursal_nombre or _nombre_sucursal(payload.sucursal_id)
    
    supabase = _get_supabase_client_safe()
    if supabase:
        try:
            insert_data = {
                "id": new_id,
                "nombre": payload.nombre,
                "canal": payload.canal,
                "tipo_cliente": payload.tipo_cliente,
                "sucursal_id": _sucursal_a_db(payload.sucursal_id),
                "moneda": payload.moneda,
                "activo": payload.activo,
            }
            res = supabase.table("listas_precios").insert(insert_data).execute()
            if res.data and len(res.data) > 0:
                row = res.data[0]
                return ListaPrecioResponse(
                    id=str(row["id"]),
                    nombre=row["nombre"],
                    canal=row["canal"],
                    tipo_cliente=row["tipo_cliente"],
                    sucursal_id=payload.sucursal_id,
                    sucursal_nombre=suc_nombre,
                    moneda=row.get("moneda", payload.moneda),
                    activo=row.get("activo", True),
                    total_items=0,
                    items=[],
                    created_at=row.get("created_at")
                )
        except Exception as e:
            logger.warning(f"Error insertando en Supabase listas_precios: {e}")

    # Almacenar en local fallback
    _LOCAL_LISTAS_PRECIOS[new_id] = {
        "id": new_id,
        "nombre": payload.nombre,
        "canal": payload.canal,
        "tipo_cliente": payload.tipo_cliente,
        "sucursal_id": payload.sucursal_id,
        "sucursal_nombre": suc_nombre,
        "moneda": payload.moneda,
        "activo": payload.activo,
        "created_at": datetime.now(timezone.utc)
    }

    return ListaPrecioResponse(
        id=new_id,
        nombre=payload.nombre,
        canal=payload.canal,
        tipo_cliente=payload.tipo_cliente,
        sucursal_id=payload.sucursal_id,
        sucursal_nombre=suc_nombre,
        moneda=payload.moneda,
        activo=payload.activo,
        total_items=0,
        items=[],
        created_at=_LOCAL_LISTAS_PRECIOS[new_id]["created_at"]
    )

@router.put("/listas-precios/{lista_id}", response_model=ListaPrecioResponse)
@require_jwt_claims("sub", allowed_roles={"administrador", "gerente_comercial"})
async def actualizar_lista_precio(
    lista_id: str,
    payload: ListaPrecioUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    RF-04: Actualiza parámetros de una lista de precios existente.
    """
    supabase = _get_supabase_client_safe()
    if supabase:
        try:
            update_data = {}
            if payload.nombre is not None: update_data["nombre"] = payload.nombre
            if payload.canal is not None: update_data["canal"] = payload.canal
            if payload.tipo_cliente is not None: update_data["tipo_cliente"] = payload.tipo_cliente
            if payload.sucursal_id is not None: update_data["sucursal_id"] = _sucursal_a_db(payload.sucursal_id)
            if payload.moneda is not None: update_data["moneda"] = payload.moneda
            if payload.activo is not None: update_data["activo"] = payload.activo
            if update_data:
                res = supabase.table("listas_precios").update(update_data).eq("id", lista_id).execute()
                if res.data and len(res.data) > 0:
                    row = res.data[0]
                    codigo = _sucursal_desde_db(row.get("sucursal_id"))
                    return _lista_precio_response({**row, "sucursal_id": codigo, "sucursal_nombre": _nombre_sucursal(codigo)})
        except Exception as e:
            logger.warning(f"Error actualizando lista de precios en Supabase: {e}")

    if lista_id in _LOCAL_LISTAS_PRECIOS:
        lp = _LOCAL_LISTAS_PRECIOS[lista_id]
        if payload.nombre is not None: lp["nombre"] = payload.nombre
        if payload.canal is not None: lp["canal"] = payload.canal
        if payload.tipo_cliente is not None: lp["tipo_cliente"] = payload.tipo_cliente
        if payload.sucursal_id is not None: lp["sucursal_id"] = payload.sucursal_id
        if payload.sucursal_nombre is not None: lp["sucursal_nombre"] = payload.sucursal_nombre
        if payload.moneda is not None: lp["moneda"] = payload.moneda
        if payload.activo is not None: lp["activo"] = payload.activo
        return ListaPrecioResponse(**lp, total_items=0, items=[])

    raise HTTPException(status_code=404, detail="Lista de precios no encontrada")

@router.delete("/listas-precios/{lista_id}", status_code=status.HTTP_204_NO_CONTENT)
@require_jwt_claims("sub", allowed_roles={"administrador", "gerente_comercial"})
async def eliminar_lista_precio(
    lista_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    RF-04: Elimina una lista de precios.
    """
    supabase = _get_supabase_client_safe()
    if supabase:
        try:
            supabase.table("listas_precios").delete().eq("id", lista_id).execute()
        except Exception:
            pass

    if lista_id in _LOCAL_LISTAS_PRECIOS:
        del _LOCAL_LISTAS_PRECIOS[lista_id]
        # Limpiar items asociados
        keys_to_del = [k for k, v in _LOCAL_PRECIOS_ITEMS.items() if v["lista_precio_id"] == lista_id]
        for k in keys_to_del:
            del _LOCAL_PRECIOS_ITEMS[k]

    return None

@router.get("/listas-precios/{lista_id}/items", response_model=List[PrecioItemResponse])
async def listar_items_lista_precio(lista_id: str):
    """
    RF-04: Lista las tarifas específicas por variante asignadas a esta lista de precios.
    """
    supabase = _get_supabase_client_safe()
    return _items_precio_response(_obtener_items_precios(supabase, lista_id), _fetch_all_products(supabase))


@router.get("/productos/{product_id}/precios", response_model=List[PrecioItemResponse])
async def listar_precios_producto(product_id: str):
    """RF-04: Tarifas diferenciadas de un producto (o sus variantes) en todas las listas."""
    supabase = _get_supabase_client_safe()
    universo = _fetch_all_products(supabase)
    producto = _buscar_producto_por_id(universo, product_id)
    claves = {product_id}
    if producto:
        claves |= {str(producto.id)} | {str(v.id) for v in producto.variantes}
    items = [item for item in _obtener_items_precios(supabase) if item["variante_id"] in claves]
    return _items_precio_response(items, universo)


def _items_precio_response(items: List[Dict[str, Any]], universo: List[ProductoResponse]) -> List[PrecioItemResponse]:
    respuesta = []
    for item in items:
        producto = _buscar_producto_por_id(universo, item["variante_id"])
        respuesta.append(PrecioItemResponse(
            id=str(item["id"]),
            lista_precio_id=item["lista_precio_id"],
            variante_id=item["variante_id"],
            sku=producto.sku if producto else item.get("sku"),
            nombre=producto.nombre if producto else item.get("nombre"),
            precio=Decimal(str(item["precio"])),
            fecha_inicio=item.get("fecha_inicio"),
            fecha_fin=item.get("fecha_fin"),
        ))
    return respuesta


def _asegurar_lista_persistida(supabase: Any, lista_id: str) -> None:
    lista = _LOCAL_LISTAS_PRECIOS.get(lista_id)
    if not lista:
        return
    supabase.table("listas_precios").upsert({
        "id": lista_id,
        "nombre": lista["nombre"],
        "canal": lista["canal"],
        "tipo_cliente": lista["tipo_cliente"],
        "sucursal_id": _sucursal_a_db(lista.get("sucursal_id")),
        "moneda": lista.get("moneda", "BOB"),
        "activo": lista.get("activo", True),
    }, on_conflict="id").execute()

@router.post("/listas-precios/{lista_id}/items", response_model=PrecioItemResponse, status_code=status.HTTP_201_CREATED)
@require_jwt_claims("sub", allowed_roles={"administrador", "gerente_comercial"})
async def asignar_precio_item(
    lista_id: str,
    payload: PrecioItemCreate,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    RF-04: Asigna o actualiza una tarifa específica para una variante en la lista de precios.
    """
    new_id = str(uuid4())
    supabase = _get_supabase_client_safe()
    producto = _buscar_producto_por_id(_fetch_all_products(supabase), payload.variante_id)
    sku_ref = producto.sku if producto else "SKU-ITEM"
    nombre_ref = producto.nombre if producto else "Producto Variante"
    # precios_items referencia variantes: un ID de producto se guarda sobre su variante principal.
    variante_id = payload.variante_id
    if producto and str(producto.id) == payload.variante_id and producto.variantes:
        variante_id = str(producto.variantes[0].id)
    fecha_inicio = payload.fecha_inicio or datetime.now(timezone.utc)

    if supabase and producto and not _es_producto_local(producto):
        try:
            _asegurar_lista_persistida(supabase, lista_id)
            upsert_data = {
                "lista_precio_id": lista_id,
                "variante_id": variante_id,
                "precio": float(payload.precio),
                "fecha_inicio": fecha_inicio.isoformat(),
                "fecha_fin": payload.fecha_fin.isoformat() if payload.fecha_fin else None
            }
            res = supabase.table("precios_items").upsert(upsert_data, on_conflict="lista_precio_id,variante_id").execute()
            if res.data and len(res.data) > 0:
                row = res.data[0]
                return PrecioItemResponse(
                    id=str(row["id"]),
                    lista_precio_id=str(row["lista_precio_id"]),
                    variante_id=str(row["variante_id"]),
                    sku=sku_ref,
                    nombre=nombre_ref,
                    precio=Decimal(str(row["precio"])),
                    fecha_inicio=row.get("fecha_inicio"),
                    fecha_fin=row.get("fecha_fin")
                )
        except Exception as e:
            logger.warning(f"Error upsert precios_items en Supabase: {e}")

    # Local fallback
    item_key = f"{lista_id}_{variante_id}"
    _LOCAL_PRECIOS_ITEMS[item_key] = {
        "id": new_id,
        "lista_precio_id": lista_id,
        "variante_id": variante_id,
        "sku": sku_ref,
        "nombre": nombre_ref,
        "precio": payload.precio,
        "fecha_inicio": fecha_inicio,
        "fecha_fin": payload.fecha_fin
    }

    return PrecioItemResponse(
        id=new_id,
        lista_precio_id=lista_id,
        variante_id=variante_id,
        sku=sku_ref,
        nombre=nombre_ref,
        precio=payload.precio,
        fecha_inicio=_LOCAL_PRECIOS_ITEMS[item_key]["fecha_inicio"],
        fecha_fin=_LOCAL_PRECIOS_ITEMS[item_key]["fecha_fin"]
    )

@router.delete("/listas-precios/{lista_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
@require_jwt_claims("sub", allowed_roles={"administrador", "gerente_comercial"})
async def eliminar_precio_item(
    lista_id: str,
    item_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    supabase = _get_supabase_client_safe()
    if supabase:
        try:
            supabase.table("precios_items").delete().eq("id", item_id).execute()
        except Exception:
            pass

    # Local fallback
    keys_to_del = [k for k, v in _LOCAL_PRECIOS_ITEMS.items() if v["id"] == item_id or k == item_id]
    for k in keys_to_del:
        del _LOCAL_PRECIOS_ITEMS[k]

    return None

# ==============================================================================
# MOTOR JERÁRQUICO DE RESOLUCIÓN DE PRECIOS (US-04 / RF-04)
# Priorización: Cliente B2B > Sucursal Específica > Canal General > Base Catálogo
# ==============================================================================
@router.get(
    "/precios/resolver",
    response_model=PrecioResolucionResponse
)
async def resolver_precio(
    variante_id: str,
    canal: str = Query(..., pattern="^(web|pos|b2b)$"),
    tipo_cliente: str = Query(
        "retail",
        pattern="^(retail|corporativo_b2b)$"
    ),
    sucursal_id: Optional[str] = None
):
    """
    US-04 / RF-04:
    Motor jerárquico de resolución de precios diferenciados:
    1. Si tipo_cliente == 'corporativo_b2b', busca primero lista B2B preferencial.
    2. Si se especifica sucursal_id, busca lista activa de esa sucursal en el canal dado.
    3. Si no, busca lista general del canal (sin sucursal asociada).
    4. Fallback: Precio base de la variante o producto del catálogo.
    """
    variante_str = str(variante_id)
    return _resolver_precios([variante_str], canal, tipo_cliente, sucursal_id)[variante_str]


@router.get("/precios/resolver-lote", response_model=Dict[str, PrecioResolucionResponse])
async def resolver_precios_lote(
    variante_ids: str = Query(..., description="IDs de producto o variante separados por coma"),
    canal: str = Query(..., pattern="^(web|pos|b2b)$"),
    tipo_cliente: str = Query("retail", pattern="^(retail|corporativo_b2b)$"),
    sucursal_id: Optional[str] = None,
):
    """RF-04: Resuelve en una sola consulta los precios de varios productos para un canal/cliente/sucursal."""
    identificadores = list(dict.fromkeys(i.strip() for i in variante_ids.split(",") if i.strip()))
    if not identificadores or len(identificadores) > 200:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Envía entre 1 y 200 identificadores.")
    return _resolver_precios(identificadores, canal, tipo_cliente, sucursal_id)


def _fecha_tarifa(valor: Any) -> Optional[datetime]:
    if not valor:
        return None
    if isinstance(valor, datetime):
        fecha = valor
    else:
        # Python 3.10 solo acepta fracciones de 3 o 6 dígitos; Supabase puede devolver otras longitudes.
        texto = re.sub(r"\.(\d+)", lambda m: "." + m.group(1)[:6].ljust(6, "0"), str(valor).replace("Z", "+00:00"), count=1)
        fecha = datetime.fromisoformat(texto)
    return fecha if fecha.tzinfo else fecha.replace(tzinfo=timezone.utc)


def _resolver_precios(
    identificadores: List[str],
    canal: str,
    tipo_cliente: str,
    sucursal_id: Optional[str],
) -> Dict[str, PrecioResolucionResponse]:
    """
    Jerarquía US-04: Cliente B2B > Sucursal específica > Canal general > Precio base del catálogo.
    Solo participan listas activas del mismo canal, tipo de cliente compatible y sucursal coincidente o general.
    """
    ahora = datetime.now(timezone.utc)
    supabase = _get_supabase_client_safe()
    universo = _fetch_all_products(supabase)
    tipos_compatibles = {tipo_cliente} | ({"retail"} if tipo_cliente == "corporativo_b2b" else set())

    def aplicable(lista: Dict[str, Any]) -> bool:
        return (
            bool(lista.get("activo", True))
            and lista.get("canal") == canal
            and lista.get("tipo_cliente", "retail") in tipos_compatibles
            and (not lista.get("sucursal_id") or lista.get("sucursal_id") == sucursal_id)
        )

    def prioridad(lista: Dict[str, Any]) -> int:
        peso = 0
        if tipo_cliente == "corporativo_b2b" and lista.get("tipo_cliente") == "corporativo_b2b":
            peso += 100
        if sucursal_id and lista.get("sucursal_id") == sucursal_id:
            peso += 50
        return peso

    listas = sorted((lista for lista in _obtener_listas_precios(supabase) if aplicable(lista)), key=prioridad, reverse=True)
    indice = {(item["lista_precio_id"], item["variante_id"]): item for item in _obtener_items_precios(supabase)}

    resultado: Dict[str, PrecioResolucionResponse] = {}
    for identificador in identificadores:
        producto = _buscar_producto_por_id(universo, identificador)
        claves = [identificador]
        if producto:
            claves += [str(producto.id)] + [str(v.id) for v in producto.variantes]

        resolucion: Optional[PrecioResolucionResponse] = None
        for lista in listas:
            for clave in claves:
                item = indice.get((lista["id"], clave))
                if not item:
                    continue
                inicio = _fecha_tarifa(item.get("fecha_inicio")) or ahora
                fin = _fecha_tarifa(item.get("fecha_fin"))
                if inicio <= ahora and (fin is None or ahora <= fin):
                    resolucion = PrecioResolucionResponse(
                        lista_precio_id=lista["id"],
                        lista_nombre=lista["nombre"],
                        variante_id=identificador,
                        precio=Decimal(str(item["precio"])),
                        moneda=lista.get("moneda") or "BOB",
                        canal=lista["canal"],
                        tipo_cliente=lista["tipo_cliente"],
                        sucursal_id=lista.get("sucursal_id"),
                        fecha_inicio=inicio.isoformat(),
                        fecha_fin=fin.isoformat() if fin else None,
                    )
                    break
            if resolucion:
                break

        if not resolucion:
            precio_base = Decimal(str(producto.precio)) if producto else Decimal("150.00")
            # Sin lista explícita, el cliente corporativo recibe la tarifa mayorista estándar (-10%).
            if tipo_cliente == "corporativo_b2b":
                precio_base = (precio_base * Decimal("0.90")).quantize(Decimal("0.01"))
            resolucion = PrecioResolucionResponse(
                lista_nombre=f"Tarifa Base Catálogo ({canal.upper()} - {tipo_cliente})",
                variante_id=identificador,
                precio=precio_base,
                moneda="BOB",
                canal=canal,
                tipo_cliente=tipo_cliente,
                fecha_inicio=ahora.isoformat(),
            )
        resultado[identificador] = resolucion
    return resultado
