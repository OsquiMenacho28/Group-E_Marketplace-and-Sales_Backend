from typing import List, Optional, Dict, Any
from uuid import UUID
from decimal import Decimal
from datetime import datetime, timezone
from pydantic import BaseModel, Field

class CategoriaBase(BaseModel):
    nombre: str
    descripcion: Optional[str] = None
    padre_id: Optional[UUID] = None
    atributos_dinamicos: List[str] = []

class CategoriaCreate(CategoriaBase):
    pass

class CategoriaUpdate(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    padre_id: Optional[UUID] = None
    atributos_dinamicos: Optional[List[str]] = None
    activo: Optional[bool] = None

class CategoriaResponse(CategoriaBase):
    id: UUID
    activo: bool = True

class VarianteBase(BaseModel):
    sku: str
    nombre_variante: str
    atributos: Dict[str, Any] = {}
    precio: Decimal = Field(..., ge=0)
    precio_costo: Decimal = Field(default=Decimal("0.0"), ge=0)
    codigo_barras: Optional[str] = None

class VarianteResponse(VarianteBase):
    id: UUID
    producto_id: UUID

class ImagenProductoCreate(BaseModel):
    data_url: str = Field(..., min_length=32, max_length=7_000_000)
    nombre: Optional[str] = Field(default=None, max_length=160)

class ImagenProductoResponse(BaseModel):
    id: UUID
    url: str
    nombre: Optional[str] = None
    es_principal: bool = False
    orden: int = 0

class ProductoCreate(BaseModel):
    sku: str
    nombre: str
    descripcion: Optional[str] = None
    marca: Optional[str] = None
    categoria_id: UUID
    precio: Decimal = Field(..., ge=0)
    variantes: List[VarianteBase] = []
    imagenes: List[ImagenProductoCreate] = Field(default_factory=list, max_length=5)

class ProductoResponse(BaseModel):
    id: UUID
    sku: str
    nombre: str
    descripcion: Optional[str] = None
    marca: Optional[str] = None
    categoria_id: UUID
    estado: str = "publicado"
    variantes: List[VarianteResponse] = []
    precio: Decimal = Field(default=Decimal("0"), ge=0)
    stock: int = 10
    categorias: Optional[CategoriaResponse] = None
    imagenes_producto: List[ImagenProductoResponse] = []
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class FacetItem(BaseModel):
    id: str
    etiqueta: str
    total: int
    seleccionado: bool = False

class RangoPrecioFacet(BaseModel):
    min: float = 0.0
    max: float = 0.0

class FacetasCatalogo(BaseModel):
    categorias: List[FacetItem] = []
    marcas: List[FacetItem] = []
    precio: RangoPrecioFacet = Field(default_factory=RangoPrecioFacet)
    en_stock: int = 0
    total_general: int = 0

class BusquedaFacetadaResponse(BaseModel):
    items: List[ProductoResponse] = []
    total_coincidencias: int = 0
    pagina: int = 1
    limite: int = 20
    facetas: FacetasCatalogo = Field(default_factory=FacetasCatalogo)

class SugerenciaItem(BaseModel):
    id: UUID
    nombre: str
    sku: str
    categoria: str
    marca: Optional[str] = None
    precio: Decimal = Field(default=Decimal("0"), ge=0)
    imagen_url: Optional[str] = None
    stock: int = 0

class ProductoUpdate(BaseModel):
    """RF-08: Actualización parcial de producto que dispara sincronización multicanal."""
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    marca: Optional[str] = None
    categoria_id: Optional[UUID] = None
    estado: Optional[str] = None
    precio: Optional[Decimal] = Field(default=None, ge=0, description="Actualiza el precio de la variante principal")
    atributos: Optional[Dict[str, Any]] = None

# ------------------------------------------------------------------------------
# RF-08: Sincronización Multicanal (delta por updated_at + eventos SSE)
# ------------------------------------------------------------------------------
class SyncCatalogoItem(BaseModel):
    id: UUID
    sku: str
    nombre: str
    precio_referencia: Decimal
    estado: str
    updated_at: datetime
    accion: str = Field(default="upsert", description="upsert | baja")

class SyncCatalogoResponse(BaseModel):
    items: List[SyncCatalogoItem]
    cursor_siguiente: Optional[str] = None
    hay_mas: bool = False
    servidor_timestamp: datetime

class SyncStatusResponse(BaseModel):
    suscriptores_activos: int
    total_productos: int
    ultima_sincronizacion: Optional[datetime] = None
    eventos_recientes: List[Dict[str, Any]] = []
    estado: str = "operativo"

# ------------------------------------------------------------------------------
# RF-07: Disponibilidad de Stock (con caché Redis TTL 30s, RIO-INV-01)
# ------------------------------------------------------------------------------
class StockDisponibilidadResponse(BaseModel):
    sku: str
    sucursal_id: Optional[str] = None
    stock_disponible: int
    origen: str = Field(description="cache | erp")
    modo: Optional[str] = Field(default=None, description="mock_fallback cuando el ERP real no está disponible")

# ------------------------------------------------------------------------------
# Consulta Rápida de Stock Multi-Sucursal (Modal F3, extensión de RIO-INV-01)
# ------------------------------------------------------------------------------
class StockSucursal(BaseModel):
    sucursal_id: str
    sucursal_nombre: str
    stock_disponible: int

class ProductoStockResumen(BaseModel):
    producto_id: Optional[UUID] = None
    sku: str
    nombre: str
    stock_total: int
    sucursales: List[StockSucursal] = []

class BusquedaStockResponse(BaseModel):
    query: str
    resultados: List[ProductoStockResumen] = []
    origen_cache: bool = False

class PrecioResolucionResponse(BaseModel):
    lista_precio_id: Optional[str] = None
    lista_nombre: str
    variante_id: str
    precio: Decimal
    moneda: str
    canal: str
    tipo_cliente: str
    sucursal_id: Optional[str] = None
    fecha_inicio: str
    fecha_fin: Optional[str] = None

class ItemReordenarImagen(BaseModel):
    id: UUID
    orden: int

class ReordenarImagenesRequest(BaseModel):
    ordenes: List[ItemReordenarImagen]

# ==============================================================================
# RF-04 / US-04: LISTAS DE PRECIOS DIFERENCIADAS (CANAL, SUCURSAL, TIPO CLIENTE)
# ==============================================================================
class ListaPrecioCreate(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=100)
    canal: str = Field(..., pattern="^(web|pos|b2b)$")
    tipo_cliente: str = Field("retail", pattern="^(retail|corporativo_b2b)$")
    sucursal_id: Optional[str] = None
    sucursal_nombre: Optional[str] = None
    moneda: str = Field("BOB", pattern="^(BOB|USD)$")
    activo: bool = True

class ListaPrecioUpdate(BaseModel):
    nombre: Optional[str] = None
    canal: Optional[str] = None
    tipo_cliente: Optional[str] = None
    sucursal_id: Optional[str] = None
    sucursal_nombre: Optional[str] = None
    moneda: Optional[str] = None
    activo: Optional[bool] = None

class PrecioItemCreate(BaseModel):
    variante_id: str
    precio: Decimal = Field(..., ge=0)
    fecha_inicio: Optional[datetime] = None
    fecha_fin: Optional[datetime] = None

class PrecioItemResponse(BaseModel):
    id: str
    lista_precio_id: str
    variante_id: str
    sku: Optional[str] = None
    nombre: Optional[str] = None
    precio: Decimal
    fecha_inicio: Optional[datetime] = None
    fecha_fin: Optional[datetime] = None

class ListaPrecioResponse(BaseModel):
    id: str
    nombre: str
    canal: str
    tipo_cliente: str
    sucursal_id: Optional[str] = None
    sucursal_nombre: Optional[str] = None
    moneda: str
    activo: bool
    total_items: Optional[int] = 0
    items: Optional[List[PrecioItemResponse]] = []
    created_at: Optional[datetime] = None
