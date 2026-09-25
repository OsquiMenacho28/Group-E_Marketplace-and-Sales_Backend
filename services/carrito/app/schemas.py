from typing import List, Optional, Union, Dict, Any
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
    cliente_id: Union[UUID, str]
    direccion_id: Optional[Union[UUID, str]] = None
    tipo_despacho: str = "domicilio" # domicilio | retiro_sucursal
    metodo_pago: str = "qr"          # tarjeta | qr | pasarela

class CheckoutInitResponse(BaseModel):
    reserva_id: str
    ttl_expira_en_segundos: int = 900
    expira_en_timestamp: Optional[float] = None
    monto_total: Decimal
    metodo_pago: str
    status: str = "RESERVA_CONFIRMADA"
    items_reservados: List[ItemCarritoResponse] = []

class ReservaConsultaResponse(BaseModel):
    reserva_id: str
    segundos_restantes: int
    estado: str
    items: List[Dict[str, Any]] = []
    monto_total: Optional[Decimal] = None

class CancelarReservaResponse(BaseModel):
    reserva_id: str
    status: str = "RESERVA_CANCELADA"
    mensaje: str = "Reserva liberada exitosamente en Inventarios y Redis"

class WishlistAdd(BaseModel):
    variante_id: UUID

class WishlistResponse(BaseModel):
    id: UUID
    cliente_id: UUID
    variante_id: UUID
    created_at: datetime