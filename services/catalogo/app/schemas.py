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
    estado: Optional[str] = None
    precio: Optional[Decimal] = Field(default=None, ge=0, description="Actualiza el precio de la variante principal")

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
