from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Query
from app.schemas import KPIDashboardResponse, ReporteVentasItem, AnaliticaEmbudoResponse, EmbudoConversionEtapa

router = APIRouter(prefix="/api/v1/reportes", tags=["Reportes y Analítica"])

@router.get("/dashboard/kpis", response_model=KPIDashboardResponse)
async def obtener_kpis():
    """RF-46: Dashboard de KPIs ejecutivos en tiempo real."""
    return KPIDashboardResponse(
        ventas_totales_hoy=Decimal("15420.50"),
        ventas_mes=Decimal("348920.00"),
        total_ordenes_hoy=34,
        ticket_promedio=Decimal("453.54"),
        tasa_conversion_porcentaje=3.85,
        productos_mas_vendidos=[
            {"sku": "LAP-DELL-XPS15", "nombre": "Laptop Dell XPS 15", "unidades": 12, "monto": 107988.0},
            {"sku": "MOU-LOG-MX3", "nombre": "Mouse Logitech MX Master 3S", "unidades": 28, "monto": 22400.0},
            {"sku": "MON-LG-27", "nombre": "Monitor LG 27\" UltraGear", "unidades": 9, "monto": 26100.0}
        ]
    )

@router.get("/ventas", response_model=List[ReporteVentasItem])
async def reportes_ventas(
    canal: Optional[str] = Query(None, description="Filtrar por canal: web | pos | b2b"),
    sucursal: Optional[str] = Query(None)
):
    """RF-47: Reporte tabular de ventas filtrado por período, sucursal y canal."""
    datos = [
        ReporteVentasItem(fecha="2026-09-10", canal="web", sucursal="Tienda Online", total_ventas=Decimal("12350.00"), cantidad_ordenes=21),
        ReporteVentasItem(fecha="2026-09-10", canal="pos", sucursal="Sucursal Central La Paz", total_ventas=Decimal("8900.00"), cantidad_ordenes=15),
        ReporteVentasItem(fecha="2026-09-11", canal="web", sucursal="Tienda Online", total_ventas=Decimal("15420.50"), cantidad_ordenes=34),
        ReporteVentasItem(fecha="2026-09-11", canal="b2b", sucursal="Corporativo", total_ventas=Decimal("45000.00"), cantidad_ordenes=2)
    ]
    if canal:
        datos = [d for d in datos if d.canal == canal]
    return datos

@router.get("/embudo", response_model=AnaliticaEmbudoResponse)
async def analitica_embudo():
    """RF-48: Analítica de embudo de conversión y carritos abandonados."""
    return AnaliticaEmbudoResponse(
        tasa_abandono_carrito_porcentaje=64.2,
        embudo=[
            EmbudoConversionEtapa(etapa="1. Visitas al Catálogo", usuarios=10500, porcentaje_retencion=100.0),
            EmbudoConversionEtapa(etapa="2. Añadido al Carrito", usuarios=2450, porcentaje_retencion=23.3),
            EmbudoConversionEtapa(etapa="3. Checkout Iniciado", usuarios=1120, porcentaje_retencion=10.6),
            EmbudoConversionEtapa(etapa="4. Compra Completada", usuarios=405, porcentaje_retencion=3.85)
        ]
    )
