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

class VentaPOSResponse(BaseModel):
    orden_id: UUID
    codigo_orden: str
    total: Decimal
    metodo_pago: str
    numero_factura: Optional[int] = None
    cuf: Optional[str] = None
    ticket_impresion: str

class VentaSuspendida(BaseModel):
    id: str
    cliente_referencia: str
    items: List[ItemVentaPOS]
    subtotal: Decimal

# ============================================================================
# HISTORIA KAN-10 / KAN-27: RETIRO EN SUCURSAL CLICK & COLLECT (RF-11)
# SUBTAREAS KAN-324 Y KAN-325
# ============================================================================
class ValidarRetiroRequest(BaseModel):
    codigo: str = Field(..., description="Código seguro de retiro (RET-XXXX), código de orden (ORD-XXXX) o payload de código QR")
    sucursal_id: Optional[str] = None

class DetalleItemRetiro(BaseModel):
    sku: str
    nombre_producto: str
    cantidad: int
    precio_unitario: Decimal
    total_linea: Decimal

class AuditoriaDespachoInfo(BaseModel):
    fecha_entrega: str
    cajero_id: Optional[str] = None
    cajero_nombre: str
    sucursal_id: Optional[str] = None
    sucursal_nombre: str
    receptor_nombre: str
    receptor_documento: str
    receptor_tipo: str # titular | tercero_autorizado
    receptor_telefono: Optional[str] = None
    observaciones: Optional[str] = None
    numero_acta: Optional[str] = None

class PedidoRetiroResponse(BaseModel):
    orden_id: UUID
    codigo_orden: str
    codigo_retiro: str
    codigo_qr: Optional[str] = None
    estado: str
    es_entregable: bool
    motivo_rechazo: Optional[str] = None
    sucursal_id: Optional[str] = None
    sucursal_nombre: str
    fecha_compra: str
    cliente_nombre: str
    cliente_documento: str
    cliente_telefono: Optional[str] = None
    cliente_email: Optional[str] = None
    subtotal: Decimal
    descuento: Decimal = Decimal("0.0")
    total: Decimal
    metodo_pago: Optional[str] = "aprobado"
    cuf_factura: Optional[str] = None
    numero_factura: Optional[int] = None
    items: List[DetalleItemRetiro]
    despacho: Optional[AuditoriaDespachoInfo] = None

class ConfirmarEntregaRequest(BaseModel):
    orden_id: UUID
    codigo_retiro: str
    receptor_nombre: str = Field(..., min_length=2)
    receptor_documento: str = Field(..., min_length=4)
    receptor_tipo: str = "titular" # titular | tercero_autorizado
    receptor_telefono: Optional[str] = None
    observaciones: Optional[str] = None
    cajero_id: Optional[str] = None
    cajero_nombre: Optional[str] = "Cajero de Turno"
    sucursal_id: Optional[str] = None
    sucursal_nombre: Optional[str] = "Sucursal Central"

class ConfirmarEntregaResponse(BaseModel):
    success: bool
    orden_id: UUID
    codigo_orden: str
    codigo_retiro: str
    nuevo_estado: str
    fecha_entrega: str
    receptor_nombre: str
    receptor_documento: str
    receptor_tipo: str
    cajero_nombre: str
    comprobante_entrega: dict
    mensaje: str
