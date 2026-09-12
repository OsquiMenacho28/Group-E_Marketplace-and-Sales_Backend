import uuid
from typing import List
from decimal import Decimal
from fastapi import APIRouter, HTTPException, status
from app.schemas import (
    AbrirCajaRequest, CerrarCajaRequest, CajaResponse,
    VentaPOSRequest, VentaPOSResponse, VentaSuspendida
)
from backend.shared.erp_clients.pagos import pagos_client
from backend.shared.erp_clients.inventarios import inventarios_client

router = APIRouter(prefix="/api/v1/pos", tags=["Punto de Venta"])

_CAJAS_ACTIVAS = {}
_VENTAS_SUSPENDIDAS = {}

@router.post("/caja/abrir", response_model=CajaResponse, status_code=status.HTTP_201_CREATED)
async def abrir_caja(payload: AbrirCajaRequest):
    """RF-09: Apertura de turno de caja con fondo inicial."""
    caja_id = uuid.uuid4()
    caja = CajaResponse(
        id=caja_id,
        sucursal_id=payload.sucursal_id,
        cajero_id=payload.cajero_id,
        fondo_inicial=payload.fondo_inicial,
        estado="abierta"
    )
    _CAJAS_ACTIVAS[str(caja_id)] = caja
    return caja

@router.post("/caja/{caja_id}/cerrar", response_model=CajaResponse)
async def cerrar_caja(caja_id: uuid.UUID, payload: CerrarCajaRequest):
    """RF-09: Cierre y arqueo de caja por turno."""
    caja = _CAJAS_ACTIVAS.get(str(caja_id))
    if not caja:
        raise HTTPException(status_code=404, detail="Caja no encontrada")

    total_esperado = caja.fondo_inicial + caja.total_efectivo
    caja.diferencia = payload.monto_cierre_real - total_esperado
    caja.estado = "cerrada"
    return caja

@router.post("/ventas/cobrar", response_model=VentaPOSResponse, status_code=status.HTTP_201_CREATED)
async def procesar_venta_pos(payload: VentaPOSRequest):
    """RF-10: Venta presencial rápida y emisión de ticket/factura."""
    caja = _CAJAS_ACTIVAS.get(str(payload.caja_id))
    if not caja or caja.estado != "abierta":
        raise HTTPException(status_code=403, detail="La caja no está abierta para procesar ventas")

    total = sum(i.cantidad * i.precio_unitario for i in payload.items)
    orden_id = uuid.uuid4()
    codigo_orden = f"POS-{uuid.uuid4().hex[:6].upper()}"

    # Acumular en caja
    if payload.metodo_pago == "efectivo":
        caja.total_efectivo += total
    elif payload.metodo_pago == "tarjeta":
        caja.total_tarjeta += total
    else:
        caja.total_qr += total

    # Timbrado fiscal RIO-PAG-02
    factura_data = await pagos_client.emitir_factura({
        "orden_id": str(orden_id),
        "nit_ci": payload.cliente_nit_ci,
        "razon_social": payload.cliente_razon_social,
        "monto_total": float(total)
    })

    # Descuento en inventario local RIO-INV-03
    await inventarios_client.descuento_definitivo(reserva_id="pos-direct", orden_id=str(orden_id))

    ticket = f"""
    ========================================
             MAXICONECTA - SUCURSAL
    ========================================
    Orden: {codigo_orden}
    NIT/CI: {payload.cliente_nit_ci}
    Cliente: {payload.cliente_razon_social}
    Total: BOB {total:.2f}
    Método: {payload.metodo_pago.upper()}
    Factura No: {factura_data.get('numero_factura')}
    CUF: {factura_data.get('cuf')}
    ========================================
    """

    return VentaPOSResponse(
        orden_id=orden_id,
        codigo_orden=codigo_orden,
        total=total,
        metodo_pago=payload.metodo_pago,
        numero_factura=factura_data.get("numero_factura"),
        cuf=factura_data.get("cuf"),
        ticket_impresion=ticket.strip()
    )

@router.post("/ventas/suspender", status_code=status.HTTP_201_CREATED)
async def suspender_venta(payload: VentaSuspendida):
    """RF-12: Suspender transacción en caja para continuar con la fila."""
    _VENTAS_SUSPENDIDAS[payload.id] = payload
    return {"mensaje": "Venta pausada exitosamente", "id": payload.id}

@router.get("/ventas/suspendidas", response_model=List[VentaSuspendida])
async def listar_ventas_suspendidas():
    """RF-12: Recuperar lista de ventas en espera."""
    return list(_VENTAS_SUSPENDIDAS.values())

@router.delete("/ventas/suspendidas/{id}")
async def reanudar_venta_suspendida(id: str):
    """RF-12: Reanudar venta y quitar de espera."""
    if id in _VENTAS_SUSPENDIDAS:
        return _VENTAS_SUSPENDIDAS.pop(id)
    raise HTTPException(status_code=404, detail="Venta suspendida no encontrada")

@router.post("/pedidos/retiro-sucursal/validar")
async def validar_retiro_sucursal(codigo_retiro: str):
    """RF-11: Validar entrega de pedido Click & Collect en tienda."""
    return {
        "codigo_retiro": codigo_retiro,
        "estado": "ENTREGADO",
        "mensaje": "Pedido entregado presencialmente con éxito"
    }
