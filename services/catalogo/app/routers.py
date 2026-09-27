from typing import List, Optional
from uuid import UUID, uuid4
from decimal import Decimal
from datetime import datetime, timezone

from fastapi import APIRouter, Query, HTTPException, status

from app.schemas import (
    ProductoCreate,
    ProductoResponse,
    VarianteResponse,
    CategoriaResponse,
    PrecioResolucionResponse
)

from backend.shared.erp_clients.inventarios import inventarios_client
from backend.shared.database import get_supabase_client

router = APIRouter(prefix="/api/v1/catalogo", tags=["Catálogo"])

# Mock store en memoria si Supabase no está conectado
_MOCK_CATEGORIAS = [
    CategoriaResponse(id=uuid4(), nombre="Electrónica", descripcion="Dispositivos y gadgets"),
    CategoriaResponse(id=uuid4(), nombre="Hogar y Oficina", descripcion="Muebles y suministros"),
]

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
        ]
    )
]

@router.get("/categorias", response_model=List[CategoriaResponse])
async def listar_categorias():
    """RF-02: Obtener árbol de categorías."""
    return _MOCK_CATEGORIAS

@router.get("/productos", response_model=List[ProductoResponse])
async def listar_productos(
    q: Optional[str] = Query(None, description="Texto de búsqueda facetada RF-06"),
    categoria_id: Optional[UUID] = Query(None),
    precio_min: Optional[Decimal] = Query(None),
    precio_max: Optional[Decimal] = Query(None)
):
    """RF-06: Búsqueda facetada y listado de productos."""
    resultados = _MOCK_PRODUCTOS
    if q:
        q_lower = q.lower()
        resultados = [p for p in resultados if q_lower in p.nombre.lower() or q_lower in p.sku.lower()]
    return resultados

@router.get("/productos/{id}", response_model=ProductoResponse)
async def obtener_producto(id: UUID):
    """RF-01: Detalle de producto con variantes."""
    for p in _MOCK_PRODUCTOS:
        if p.id == id:
            return p
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")

@router.post("/productos", response_model=ProductoResponse, status_code=status.HTTP_201_CREATED)
async def crear_producto(payload: ProductoCreate):
    """RF-01, RF-05: Crear producto y sus variantes."""
    prod_id = uuid4()
    variantes_res = [
        VarianteResponse(
            id=uuid4(),
            producto_id=prod_id,
            sku=v.sku,
            nombre_variante=v.nombre_variante,
            atributos=v.atributos,
            precio=v.precio,
            codigo_barras=v.codigo_barras
        ) for v in payload.variantes
    ]
    nuevo_prod = ProductoResponse(
        id=prod_id,
        sku=payload.sku,
        nombre=payload.nombre,
        descripcion=payload.descripcion,
        marca=payload.marca,
        categoria_id=payload.categoria_id,
        estado="publicado",
        variantes=variantes_res
    )
    _MOCK_PRODUCTOS.append(nuevo_prod)
    return nuevo_prod

@router.get("/stock/{sku}")
async def consultar_stock(sku: str, sucursal_id: Optional[str] = None):
    """RF-07: Consulta en tiempo real vía RIO-INV-01."""
    return await inventarios_client.consultar_disponibilidad(sku, sucursal_id)

@router.get(
    "/precios/resolver",
    response_model=PrecioResolucionResponse
)
async def resolver_precio(
    variante_id: UUID,
    canal: str = Query(..., pattern="^(web|pos|b2b)$"),
    tipo_cliente: str = Query(
        "retail",
        pattern="^(retail|corporativo_b2b)$"
    ),
    sucursal_id: Optional[UUID] = None
):
    """
    KAN-297:
    Resuelve el precio vigente de una variante según:
    - canal
    - tipo de cliente
    - sucursal
    - vigencia
    """

    supabase = get_supabase_client()

    if supabase is None:
        raise HTTPException(
            status_code=503,
            detail="Supabase no está disponible."
        )

    ahora = datetime.now(timezone.utc)

    # Buscar listas de precios activas que coincidan
    # con canal, tipo de cliente y sucursal.
    query = (
        supabase
        .table("listas_precios")
        .select(
            "id,nombre,canal,tipo_cliente,sucursal_id,moneda,activo"
        )
        .eq("canal", canal)
        .eq("tipo_cliente", tipo_cliente)
        .eq("activo", True)
    )

    if sucursal_id:
        query = query.eq("sucursal_id", str(sucursal_id))

    listas_response = query.execute()

    listas = listas_response.data or []

    if not listas:
        raise HTTPException(
            status_code=404,
            detail="No existe una lista de precios activa para los criterios indicados."
        )

    # Buscar el precio vigente para la variante.
    for lista in listas:

        precios_response = (
            supabase
            .table("precios_items")
            .select(
                "lista_precio_id,variante_id,precio,fecha_inicio,fecha_fin"
            )
            .eq("lista_precio_id", lista["id"])
            .eq("variante_id", str(variante_id))
            .execute()
        )

        precios = precios_response.data or []

        for item in precios:
            fecha_inicio = datetime.fromisoformat(
                item["fecha_inicio"].replace("Z", "+00:00")
            )

            fecha_fin = None

            if item.get("fecha_fin"):
                fecha_fin = datetime.fromisoformat(
                    item["fecha_fin"].replace("Z", "+00:00")
                )

            if fecha_inicio <= ahora and (
                fecha_fin is None or ahora <= fecha_fin
            ):
                return PrecioResolucionResponse(
                    lista_precio_id=lista["id"],
                    lista_nombre=lista["nombre"],
                    variante_id=item["variante_id"],
                    precio=Decimal(str(item["precio"])),
                    moneda=lista["moneda"],
                    canal=lista["canal"],
                    tipo_cliente=lista["tipo_cliente"],
                    sucursal_id=lista.get("sucursal_id"),
                    fecha_inicio=item["fecha_inicio"],
                    fecha_fin=item.get("fecha_fin")
                )

    raise HTTPException(
        status_code=404,
        detail="No existe un precio vigente para la variante indicada."
    )