from typing import List, Optional, Union, Dict, Any
from uuid import UUID
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator

class ItemCarritoAdd(BaseModel):
    variante_id: str = Field(..., min_length=1, max_length=120)
    sku: str
    nombre: str
    cantidad: int = Field(..., gt=0)
    precio_unitario: Decimal = Field(..., ge=0)

class ItemCarritoUpdate(BaseModel):
    cantidad: int = Field(..., gt=0)

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

# ------------------------------------------------------------------------------
# RF-17: Promociones y Cupones (columnas alineadas con la tabla `cupones`)
# ------------------------------------------------------------------------------
class CuponBase(BaseModel):
    descripcion: Optional[str] = Field(default=None, max_length=200)
    tipo_descuento: str = Field(..., description="porcentaje | monto_fijo")
    valor_descuento: Decimal = Field(..., gt=0)
    monto_minimo: Decimal = Field(default=Decimal("0"), ge=0, description="Monto mínimo de compra para aplicar el cupón")
    usos_maximos: Optional[int] = Field(default=100, ge=1, description="Límite de canjes (null = ilimitado)")
    fecha_inicio: Optional[datetime] = None
    fecha_fin: Optional[datetime] = None
    activo: bool = True

    @field_validator("tipo_descuento")
    @classmethod
    def _tipo_valido(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in ("porcentaje", "monto_fijo"):
            raise ValueError("tipo_descuento debe ser 'porcentaje' o 'monto_fijo'")
        return v

    @model_validator(mode="after")
    def _coherencia(self):
        if self.tipo_descuento == "porcentaje" and self.valor_descuento > 100:
            raise ValueError("Un descuento porcentual no puede superar el 100%")
        if self.fecha_inicio and self.fecha_fin and self.fecha_fin <= self.fecha_inicio:
            raise ValueError("fecha_fin debe ser posterior a fecha_inicio")
        return self

class CuponAdminCreate(CuponBase):
    codigo: str = Field(..., min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_-]+$")

class CuponAdminUpdate(BaseModel):
    descripcion: Optional[str] = Field(default=None, max_length=200)
    tipo_descuento: Optional[str] = None
    valor_descuento: Optional[Decimal] = Field(default=None, gt=0)
    monto_minimo: Optional[Decimal] = Field(default=None, ge=0)
    usos_maximos: Optional[int] = Field(default=None, ge=1)
    fecha_inicio: Optional[datetime] = None
    fecha_fin: Optional[datetime] = None
    activo: Optional[bool] = None

    @field_validator("tipo_descuento")
    @classmethod
    def _tipo_valido(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip().lower()
        if v not in ("porcentaje", "monto_fijo"):
            raise ValueError("tipo_descuento debe ser 'porcentaje' o 'monto_fijo'")
        return v

class CuponAdminResponse(BaseModel):
    id: Optional[str] = None
    codigo: str
    descripcion: Optional[str] = None
    tipo_descuento: str
    valor_descuento: Decimal
    monto_minimo: Decimal = Decimal("0")
    usos_maximos: Optional[int] = None
    usos_actuales: int = 0
    fecha_inicio: Optional[datetime] = None
    fecha_fin: Optional[datetime] = None
    activo: bool = True
    estado_vigencia: str = Field(default="vigente", description="vigente | programado | vencido | agotado | inactivo")

class ValidarCuponRequest(BaseModel):
    codigo: str = Field(..., min_length=1)
    subtotal: Decimal = Field(..., ge=0)

class ValidarCuponResponse(BaseModel):
    valido: bool
    codigo: str
    motivo: Optional[str] = None
    mensaje: str
    descuento: Decimal = Decimal("0.00")
    tipo_descuento: Optional[str] = None
    valor_descuento: Optional[Decimal] = None
    monto_minimo: Decimal = Decimal("0.00")
    total_con_descuento: Decimal = Decimal("0.00")

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
    sku: Optional[str] = None
    nombre: Optional[str] = None
    precio: Optional[Decimal] = None
    imagen_url: Optional[str] = None