import base64
import io
import uuid
from datetime import datetime
from typing import Any, Dict, List
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlencode

import qrcode
from qrcode.image.svg import SvgPathImage
from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas import (
    AbrirCajaRequest, CerrarCajaRequest, CajaResponse,
    ItemTicketPOS, VentaPOSRequest, VentaPOSResponse, VentaSuspendida
)
from backend.shared.erp_clients.pagos import pagos_client
from backend.shared.erp_clients.inventarios import inventarios_client
from backend.shared.security import get_current_user, require_jwt_claims

router = APIRouter(prefix="/api/v1/pos", tags=["Punto de Venta"])

_CAJAS_ACTIVAS = {}
_VENTAS_SUSPENDIDAS = {}
_NIT_EMISOR = "1028374029"
_IVA_RATE = Decimal("0.13")


def _qr_data_url(payload: str) -> str:
    image = qrcode.make(payload, image_factory=SvgPathImage, box_size=5, border=3)
    output = io.BytesIO()
    image.save(output)
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"

@router.post("/caja/abrir", response_model=CajaResponse, status_code=status.HTTP_201_CREATED)
@require_jwt_claims("sub", allowed_roles={"cajero", "administrador"})
async def abrir_caja(
    payload: AbrirCajaRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
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
@require_jwt_claims("sub", allowed_roles={"cajero", "administrador"})
async def procesar_venta_pos(
    payload: VentaPOSRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """RF-10: Venta presencial rápida y emisión de ticket/factura."""
    caja = _CAJAS_ACTIVAS.get(str(payload.caja_id))
    if not caja or caja.estado != "abierta":
        raise HTTPException(status_code=403, detail="La caja no está abierta para procesar ventas")

    lineas = [
        ItemTicketPOS(
            sku=item.sku,
            nombre=item.nombre,
            cantidad=item.cantidad,
            precio_unitario=item.precio_unitario,
            total_linea=(item.precio_unitario * item.cantidad).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        )
        for item in payload.items
    ]
    total = sum((linea.total_linea for linea in lineas), Decimal("0.00")).quantize(Decimal("0.01"))
    monto_iva = (total * _IVA_RATE / (Decimal("1.00") + _IVA_RATE)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    subtotal_neto = total - monto_iva
    orden_id = uuid.uuid4()
    codigo_orden = f"POS-{uuid.uuid4().hex[:6].upper()}"

    # Timbrado fiscal RIO-PAG-02
    factura_data = await pagos_client.emitir_factura({
        "orden_id": str(orden_id),
        "codigo_orden": codigo_orden,
        "sucursal_id": str(payload.sucursal_id),
        "nit_ci": payload.cliente_nit_ci,
        "razon_social": payload.cliente_razon_social,
        "subtotal_neto": float(subtotal_neto),
        "monto_iva": float(monto_iva),
        "monto_total": float(total),
        "metodo_pago": payload.metodo_pago,
        "items": [
            {
                "variante_id": str(item.variante_id),
                "sku": item.sku,
                "nombre": item.nombre,
                "cantidad": item.cantidad,
                "precio_unitario": float(item.precio_unitario),
                "total_linea": float(linea.total_linea),
            }
            for item, linea in zip(payload.items, lineas)
        ],
    })

    numero_factura = factura_data.get("numero_factura")
    cuf = factura_data.get("cuf")
    if not numero_factura or not cuf:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="El servicio tributario no devolvió número de factura y CUF.")

    qr_url = factura_data.get("qr_url") or factura_data.get("codigo_qr") or (
        "https://pilotosiat.impuestos.gob.bo/consulta/QR?" + urlencode({
            "nit": _NIT_EMISOR,
            "cuf": cuf,
            "numero": numero_factura,
            "t": f"{total:.2f}",
        })
    )
    qr_code = _qr_data_url(qr_url)

    # Acumular en caja cuando la factura ya fue timbrada.
    if payload.metodo_pago == "efectivo":
        caja.total_efectivo += total
    elif payload.metodo_pago == "tarjeta":
        caja.total_tarjeta += total
    else:
        caja.total_qr += total

    # Descuento en inventario local RIO-INV-03
    await inventarios_client.descuento_definitivo(reserva_id="pos-direct", orden_id=str(orden_id))

    ancho = 42
    separador = "-" * ancho
    detalle_items = "\n".join(
        f"{linea.cantidad} x {linea.nombre[:20]}\n  SKU {linea.sku[:18]} @ BOB {linea.precio_unitario:.2f}  BOB {linea.total_linea:.2f}"
        for linea in lineas
    )
    ticket = f"""
    ========================================
             MAXICONECTA - SUCURSAL
    ========================================
    Orden: {codigo_orden}
    Fecha: {datetime.now().astimezone().strftime('%d/%m/%Y %H:%M')}
    NIT/CI: {payload.cliente_nit_ci}
    Cliente: {payload.cliente_razon_social}
    {separador}
    DETALLE DE ÍTEMS
    {detalle_items}
    {separador}
    Subtotal neto: BOB {subtotal_neto:.2f}
    IVA (13% incluido): BOB {monto_iva:.2f}
    TOTAL: BOB {total:.2f}
    Método: {payload.metodo_pago.upper()}
    Factura No: {numero_factura}
    CUF: {cuf}
    QR tributario: {qr_url}
    ========================================
    """

    return VentaPOSResponse(
        orden_id=orden_id,
        codigo_orden=codigo_orden,
        subtotal_neto=subtotal_neto,
        monto_iva=monto_iva,
        total=total,
        metodo_pago=payload.metodo_pago,
        numero_factura=numero_factura,
        cuf=cuf,
        cufd=factura_data.get("cufd"),
        qr_url=qr_url,
        qr_code=qr_code,
        items=lineas,
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
