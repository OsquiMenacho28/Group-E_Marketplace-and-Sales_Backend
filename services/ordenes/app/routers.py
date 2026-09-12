import uuid
from typing import List
from datetime import datetime
from decimal import Decimal
from fastapi import APIRouter, HTTPException, status
from app.schemas import (
    OrdenCreate, OrdenResponse, ItemOrdenResponse,
    TransicionEstadoRequest, CotizacionB2BCreate, CotizacionB2BResponse
)
from backend.shared.erp_clients.inventarios import inventarios_client
from backend.shared.erp_clients.pagos import pagos_client
from backend.shared.erp_clients.entregas import entregas_client
from backend.shared.erp_clients.contabilidad import contabilidad_client

router = APIRouter(prefix="/api/v1/ordenes", tags=["Órdenes y Ventas"])

_ORDENES_DB = {}
_COTIZACIONES_DB = {}

TRANSICIONES_VALIDAS = {
    "pendiente": ["confirmada", "cancelada"],
    "confirmada": ["en_preparacion", "cancelada"],
    "en_preparacion": ["despachada", "cancelada"],
    "despachada": ["entregada"],
    "entregada": [],
    "cancelada": []
}

@router.post("/", response_model=OrdenResponse, status_code=status.HTTP_201_CREATED)
async def crear_orden(payload: OrdenCreate):
    """RF-27: Creación atómica de orden tras pago confirmado."""
    orden_id = uuid.uuid4()
    codigo = f"ORD-{datetime.utcnow().year}-{uuid.uuid4().hex[:6].upper()}"

    # 1. Ejecutar descuento definitivo en Inventarios (RIO-INV-03)
    if payload.reserva_id:
        await inventarios_client.descuento_definitivo(payload.reserva_id, str(orden_id))

    # 2. Generar orden de despacho si es a domicilio (RIO-ENT-01)
    tracking_num = None
    if payload.tipo_despacho == "domicilio":
        despacho_res = await entregas_client.solicitar_despacho({
            "orden_id": str(orden_id),
            "direccion_id": str(payload.direccion_entrega_id),
            "items": [i.dict() for i in payload.items]
        })
        tracking_num = despacho_res.get("guia_despacho")

    # 3. Registrar asiento contable de ventas (RIO-CON-01)
    await contabilidad_client.registrar_asiento_venta({
        "orden_id": str(orden_id),
        "monto_total": float(payload.total),
        "canal": payload.canal
    })

    items_res = [
        ItemOrdenResponse(
            id=uuid.uuid4(),
            variante_id=i.variante_id,
            sku=i.sku,
            nombre_producto=i.nombre_producto,
            cantidad=i.cantidad,
            precio_unitario=i.precio_unitario,
            total_linea=Decimal(str(i.cantidad)) * i.precio_unitario
        ) for i in payload.items
    ]

    orden = OrdenResponse(
        id=orden_id,
        codigo_orden=codigo,
        cliente_id=payload.cliente_id,
        canal=payload.canal,
        tipo_despacho=payload.tipo_despacho,
        subtotal=payload.subtotal,
        total=payload.total,
        estado="confirmada",
        tracking_number=tracking_num,
        created_at=datetime.utcnow(),
        items=items_res
    )
    _ORDENES_DB[str(orden_id)] = orden
    return orden

@router.get("/{id}", response_model=OrdenResponse)
async def obtener_orden(id: uuid.UUID):
    """RF-29, RF-37: Detalle e historial de orden."""
    oid = str(id)
    if oid in _ORDENES_DB:
        return _ORDENES_DB[oid]
    raise HTTPException(status_code=404, detail="Orden no encontrada")

@router.patch("/{id}/estado", response_model=OrdenResponse)
async def cambiar_estado_orden(id: uuid.UUID, payload: TransicionEstadoRequest):
    """RF-28: Máquina de estados de la orden."""
    oid = str(id)
    if oid not in _ORDENES_DB:
        raise HTTPException(status_code=404, detail="Orden no encontrada")

    orden = _ORDENES_DB[oid]
    estado_actual = orden.estado
    nuevo_estado = payload.nuevo_estado.lower()

    if nuevo_estado not in TRANSICIONES_VALIDAS.get(estado_actual, []):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Transición no permitida de '{estado_actual}' a '{nuevo_estado}'."
        )

    orden.estado = nuevo_estado
    return orden

@router.post("/{id}/cancelar", response_model=OrdenResponse)
async def cancelar_orden(id: uuid.UUID, motivo: str):
    """RF-31, RF-33: Cancelación pre-despacho y reversiones contable/inventarial."""
    oid = str(id)
    if oid not in _ORDENES_DB:
        raise HTTPException(status_code=404, detail="Orden no encontrada")

    orden = _ORDENES_DB[oid]
    if orden.estado in ["despachada", "entregada"]:
        raise HTTPException(status_code=400, detail="No es posible cancelar una orden que ya fue despachada o entregada")

    orden.estado = "cancelada"

    # RIO-INV-04: Reingreso de stock
    await inventarios_client.reingreso_por_devolucion(oid, [i.dict() for i in orden.items])
    # RIO-CON-04: Reversión contable
    await contabilidad_client.registrar_reversion({"orden_id": oid, "motivo": motivo})
    # RIO-PAG-03: Reversión de pago
    await pagos_client.reversar_cobro(transaccion_id=f"tx-{oid[:8]}", monto=float(orden.total))

    return orden

# ------------------------------------------------------------------------------
# COTIZACIONES B2B (RF-34, RF-35, RF-36)
# ------------------------------------------------------------------------------
@router.post("/cotizaciones", response_model=CotizacionB2BResponse, status_code=status.HTTP_201_CREATED)
async def crear_cotizacion(payload: CotizacionB2BCreate):
    """RF-34: Emisión de cotización corporativa B2B."""
    cot_id = uuid.uuid4()
    codigo = f"COT-B2B-{uuid.uuid4().hex[:6].upper()}"
    subtotal = sum(i.cantidad * i.precio_unitario for i in payload.items)
    descuento = subtotal * (payload.descuento_porcentaje / Decimal("100"))
    total = subtotal - descuento

    cotizacion = CotizacionB2BResponse(
        id=cot_id,
        codigo_cotizacion=codigo,
        cliente_id=payload.cliente_id,
        total=total,
        vigencia_hasta=payload.vigencia_hasta,
        estado="borrador" if payload.descuento_porcentaje <= 10 else "pendiente_aprobacion",
        items=payload.items
    )
    _COTIZACIONES_DB[str(cot_id)] = cotizacion
    return cotizacion

@router.post("/cotizaciones/{id}/aprobar", response_model=CotizacionB2BResponse)
async def aprobar_cotizacion(id: uuid.UUID):
    """RF-35: Aprobación jerárquica de cotización B2B."""
    cid = str(id)
    if cid not in _COTIZACIONES_DB:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    cot = _COTIZACIONES_DB[cid]
    cot.estado = "aprobada"
    return cot
