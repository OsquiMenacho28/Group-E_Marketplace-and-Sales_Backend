from typing import List, Optional
from uuid import UUID
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, Field

class ItemCarritoAdd(BaseModel):
    variante_id: UUID
    sku: str
    nombre: str
    cantidad: int = Field(..., gt=0)
    precio_unitario: Decimal = Field(..., ge=0)

class ItemCarritoResponse(ItemCarritoAdd):
    total_linea: Decimal

class CarritoResponse(BaseModel):
    cliente_o_sesion_id: str
    items: List[ItemCarritoResponse] = []
    subtotal: Decimal = Decimal("0.0")
    descuento_cupon: Decimal = Decimal("0.0")
    cupon_codigo: Optional[str] = None
    total: Decimal = Decimal("0.0")

class AplicarCuponRequest(BaseModel):
    codigo: str

class CheckoutInitRequest(BaseModel):
    cliente_id: UUID
    direccion_id: Optional[UUID] = None
    tipo_despacho: str = "domicilio" # domicilio | retiro_sucursal
    metodo_pago: str = "tarjeta"     # tarjeta | qr | pasarela

class CheckoutInitResponse(BaseModel):
    reserva_id: str
    ttl_expira_en_segundos: int
    monto_total: Decimal
    metodo_pago: str
    status: str = "RESERVA_CONFIRMADA"

class WishlistAdd(BaseModel):
    variante_id: UUID


class WishlistResponse(BaseModel):
    id: UUID
    cliente_id: UUID
    variante_id: UUID
    created_at: datetime