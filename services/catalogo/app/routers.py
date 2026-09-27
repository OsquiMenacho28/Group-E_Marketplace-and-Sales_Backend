import base64
import binascii
import logging
import re
import unicodedata
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status

try:
    from app.schemas import (
        CategoriaResponse,
        ProductoCreate,
        ProductoResponse,
        VarianteResponse,
        ImagenProductoResponse,
        FacetItem,
        RangoPrecioFacet,
        FacetasCatalogo,
        BusquedaFacetadaResponse,
        SugerenciaItem,
    )
except (ModuleNotFoundError, ImportError):
    from backend.services.catalogo.app.schemas import (
        CategoriaResponse,
        ProductoCreate,
        ProductoResponse,
        VarianteResponse,
        ImagenProductoResponse,
        FacetItem,
        RangoPrecioFacet,
        FacetasCatalogo,
        BusquedaFacetadaResponse,
        SugerenciaItem,
    )

from backend.shared.database import get_supabase_admin_client
from backend.shared.erp_clients.inventarios import inventarios_client
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
                return [_product_response_from_db(client, r) for r in rows]
        except Exception as e:
            logger.warning(f"Error consultando productos de Supabase: {e}. Usando catálogo local.")

    return [_build_product_response(p) for p in _LOCAL_PRODUCTOS.values()]


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

    return recomendados[:limite]


# ------------------------------------------------------------------------------
# 5. LISTADO ESTÁNDAR Y DETALLE DE PRODUCTOS (COMPATIBILIDAD HACIA ATRÁS)
# ------------------------------------------------------------------------------
@router.get("/productos", response_model=List[ProductoResponse])
async def listar_productos(
    q: Optional[str] = Query(None, description="Texto de búsqueda facetada RF-06"),
    categoria_id: Optional[UUID] = Query(None),
    precio_min: Optional[Decimal] = Query(None),
    precio_max: Optional[Decimal] = Query(None),
):
    client = _get_supabase_client_safe()
    if client:
        try:
            query = client.table("productos").select("*").eq("estado", "publicado")
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
    return _product_response_from_db(client, created.data)


@router.get("/stock/{sku}")
async def consultar_stock(sku: str, sucursal_id: Optional[str] = None):
    return await inventarios_client.consultar_disponibilidad(sku, sucursal_id)
