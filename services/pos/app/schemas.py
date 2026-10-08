from typing import List, Optional
from uuid import UUID
from decimal import Decimal
from pydantic import BaseModel, Field

class AbrirCajaRequest(BaseModel):
    sucursal_id: UUID
    cajero_id: UUID
    fondo_inicial: Decimal = Field(..., ge=0)

class CerrarCajaRequest(BaseModel):
    monto_cierre_real: Decimal = Field(..., ge=0)

class CajaResponse(BaseModel):
    id: UUID
    sucursal_id: UUID
    cajero_id: UUID
    fondo_inicial: Decimal
    total_efectivo: Decimal = Decimal("0.0")
    total_tarjeta: Decimal = Decimal("0.0")
    total_qr: Decimal = Decimal("0.0")
    estado: str
    diferencia: Optional[Decimal] = None

class ItemVentaPOS(BaseModel):
    variante_id: UUID
    sku: str
    nombre: str
    cantidad: int = Field(..., gt=0)
    precio_unitario: Decimal = Field(..., ge=0)

class VentaPOSRequest(BaseModel):
    caja_id: UUID
    sucursal_id: UUID
    cliente_nit_ci: Optional[str] = "0"
    cliente_razon_social: Optional[str] = "Sin Nombre"
    items: List[ItemVentaPOS]
    metodo_pago: str = "efectivo" # efectivo | tarjeta | qr

class ItemTicketPOS(BaseModel):
    sku: str
    nombre: str
    cantidad: int
    precio_unitario: Decimal
    total_linea: Decimal

class VentaPOSResponse(BaseModel):
    orden_id: UUID
    codigo_orden: str
    subtotal_neto: Decimal
    monto_iva: Decimal
    total: Decimal
    metodo_pago: str
    numero_factura: Optional[int] = None
    cuf: Optional[str] = None
    cufd: Optional[str] = None
    qr_url: str
    qr_code: str
    items: List[ItemTicketPOS]
    ticket_impresion: str

class VentaSuspendida(BaseModel):
    id: str
    cliente_referencia: str
    items: List[ItemVentaPOS]
    subtotal: Decimal
