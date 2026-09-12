from typing import List, Dict, Any
from decimal import Decimal
from pydantic import BaseModel

class KPIDashboardResponse(BaseModel):
    ventas_totales_hoy: Decimal
    ventas_mes: Decimal
    total_ordenes_hoy: int
    ticket_promedio: Decimal
    tasa_conversion_porcentaje: float
    productos_mas_vendidos: List[Dict[str, Any]]

class ReporteVentasItem(BaseModel):
    fecha: str
    canal: str
    sucursal: str
    total_ventas: Decimal
    cantidad_ordenes: int

class EmbudoConversionEtapa(BaseModel):
    etapa: str
    usuarios: int
    porcentaje_retencion: float

class AnaliticaEmbudoResponse(BaseModel):
    tasa_abandono_carrito_porcentaje: float
    embudo: List[EmbudoConversionEtapa]
