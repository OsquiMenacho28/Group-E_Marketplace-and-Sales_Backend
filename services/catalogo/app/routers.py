from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
import base64
import binascii
import re
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.schemas import CategoriaResponse, ProductoCreate, ProductoResponse
from backend.shared.database import get_supabase_admin_client
from backend.shared.erp_clients.inventarios import inventarios_client
from backend.shared.security import get_current_user, require_jwt_claims

router = APIRouter(prefix="/api/v1/catalogo", tags=["Catálogo"])

STORAGE_BUCKET = "productos"
MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
DATA_URL_PATTERN = re.compile(r"^data:(image/(?:jpeg|png|webp));base64,([A-Za-z0-9+/=]+)$")


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


@router.get("/stock/{sku}")
async def consultar_stock(sku: str, sucursal_id: Optional[str] = None):
    return await inventarios_client.consultar_disponibilidad(sku, sucursal_id)
