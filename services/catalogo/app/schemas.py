from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
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

class ProductoCreate(BaseModel):
    sku: str
    nombre: str
    descripcion: Optional[str] = None
    marca: Optional[str] = None
    categoria_id: UUID
    variantes: List[VarianteBase] = []

class ProductoResponse(BaseModel):
    id: UUID
    sku: str
    nombre: str
    descripcion: Optional[str] = None
    marca: Optional[str] = None
    categoria_id: UUID
    estado: str = "publicado"
    variantes: List[VarianteResponse] = []
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

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
