from typing import List, Optional
from uuid import UUID
from datetime import datetime, date
from decimal import Decimal
from pydantic import BaseModel, Field

class ItemOrdenCreate(BaseModel):
    variante_id: UUID
    sku: str
    nombre_producto: str
    cantidad: int = Field(..., gt=0)
    precio_unitario: Decimal = Field(..., ge=0)

class ItemOrdenResponse(ItemOrdenCreate):
    id: UUID
    total_linea: Decimal

class OrdenCreate(BaseModel):
    cliente_id: UUID
    sucursal_id: Optional[UUID] = None
    canal: str = "web"
    tipo_despacho: str = "domicilio" # domicilio | retiro_sucursal
    direccion_entrega_id: Optional[UUID] = None
    subtotal: Decimal
    descuento: Decimal = Decimal("0.0")
    costo_envio: Decimal = Decimal("0.0")
    total: Decimal
    metodo_pago: str = "tarjeta"
    items: List[ItemOrdenCreate]
    reserva_id: Optional[str] = None

class OrdenResponse(BaseModel):
    id: UUID
    codigo_orden: str
    cliente_id: UUID
    canal: str
    tipo_despacho: str
    subtotal: Decimal
    total: Decimal
    estado: str # pendiente, confirmada, en_preparacion, despachada, entregada, cancelada
    tracking_number: Optional[str] = None
    cuf_factura: Optional[str] = None
    created_at: datetime
    items: List[ItemOrdenResponse] = []

class TransicionEstadoRequest(BaseModel):
    nuevo_estado: str

class CotizacionB2BCreate(BaseModel):
    cliente_id: UUID
    vigencia_hasta: date
    items: List[ItemOrdenCreate]
    descuento_porcentaje: Decimal = Decimal("0.0")

class CotizacionB2BResponse(BaseModel):
    id: UUID
    codigo_cotizacion: str
    cliente_id: UUID
    total: Decimal
    vigencia_hasta: date
    estado: str # borrador, pendiente_aprobacion, aprobada, rechazada, convertida
    items: List[ItemOrdenCreate] = []
