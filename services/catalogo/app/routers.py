from typing import List, Optional
from uuid import UUID, uuid4
from decimal import Decimal
from fastapi import APIRouter, Query, HTTPException, status
from app.schemas import ProductoCreate, ProductoResponse, VarianteResponse, CategoriaResponse
from backend.shared.erp_clients.inventarios import inventarios_client

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
