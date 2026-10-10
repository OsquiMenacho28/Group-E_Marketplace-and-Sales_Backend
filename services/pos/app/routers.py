import uuid
from typing import Any, Dict, List
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
try:
    from app.schemas import (
        AbrirCajaRequest, CerrarCajaRequest, CajaResponse,
        VentaPOSRequest, VentaPOSResponse, VentaSuspendida,
        ValidarRetiroRequest, DetalleItemRetiro, AuditoriaDespachoInfo,
        PedidoRetiroResponse, ConfirmarEntregaRequest, ConfirmarEntregaResponse
    )
except (ModuleNotFoundError, ImportError):
    from backend.services.pos.app.schemas import (
        AbrirCajaRequest, CerrarCajaRequest, CajaResponse,
        VentaPOSRequest, VentaPOSResponse, VentaSuspendida,
        ValidarRetiroRequest, DetalleItemRetiro, AuditoriaDespachoInfo,
        PedidoRetiroResponse, ConfirmarEntregaRequest, ConfirmarEntregaResponse
    )
from datetime import datetime
from backend.shared.database import get_supabase_admin_client
from backend.shared.erp_clients.pagos import pagos_client
from backend.shared.erp_clients.inventarios import inventarios_client
from backend.shared.security import get_current_user, require_jwt_claims
from backend.shared.redis_client import (
    save_suspended_sale,
    get_suspended_sale,
    list_suspended_sales,
    delete_suspended_sale
)

router = APIRouter(prefix="/api/v1/pos", tags=["Punto de Venta"])

_CAJAS_ACTIVAS = {}
#_VENTAS_SUSPENDIDAS = {}

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

    total = sum(i.cantidad * i.precio_unitario for i in payload.items)
    orden_id = uuid.uuid4()
    codigo_orden = f"POS-{uuid.uuid4().hex[:6].upper()}"

    # Descuento en inventario RIO-INV-03 antes de cobrar, para no vender sin stock
    consumo = await inventarios_client.descuento_directo(
        [{"sku": i.sku, "cantidad": i.cantidad} for i in payload.items],
        orden_id=str(orden_id),
    )
    if consumo.get("status") == "RECHAZADA":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=consumo.get("mensaje", "Stock insuficiente."))

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

@router.post(
    "/ventas/{caja_id}/suspender",
    status_code=status.HTTP_201_CREATED
)
async def suspender_venta(
    caja_id: uuid.UUID,
    payload: VentaSuspendida
):
    """RF-12: Suspender transacción en una caja."""

    caja = _CAJAS_ACTIVAS.get(str(caja_id))

    if not caja or caja.estado != "abierta":
        raise HTTPException(
            status_code=403,
            detail="La caja no está abierta"
        )

    await save_suspended_sale(
        str(caja_id),
        payload.id,
        payload.model_dump(mode="json")
    )

    return {
        "mensaje": "Venta pausada exitosamente",
        "id": payload.id
    }


@router.get(
    "/ventas/{caja_id}/suspendidas",
    response_model=List[VentaSuspendida]
)
async def listar_ventas_suspendidas(
    caja_id: uuid.UUID
):
    """RF-12: Recuperar lista de ventas en espera de una caja."""

    caja = _CAJAS_ACTIVAS.get(str(caja_id))

    if not caja:
        raise HTTPException(
            status_code=404,
            detail="Caja no encontrada"
        )

    ventas = await list_suspended_sales(str(caja_id))

    return [
        VentaSuspendida(**venta)
        for venta in ventas
    ]


@router.delete("/ventas/{caja_id}/suspendidas/{id}")
async def reanudar_venta_suspendida(
    caja_id: uuid.UUID,
    id: str
):
    """RF-12: Reanudar venta y quitarla de espera."""

    caja = _CAJAS_ACTIVAS.get(str(caja_id))

    if not caja:
        raise HTTPException(
            status_code=404,
            detail="Caja no encontrada"
        )

    venta = await get_suspended_sale(
        str(caja_id),
        id
    )

    if not venta:
        raise HTTPException(
            status_code=404,
            detail="Venta suspendida no encontrada"
        )

    await delete_suspended_sale(
        str(caja_id),
        id
    )

    return venta


@router.post("/ventas/suspender", status_code=status.HTTP_201_CREATED)
async def suspender_venta_global(payload: VentaSuspendida):
    """RF-12: Suspender transacción global/general."""
    caja_id = "general"
    for cid, c in _CAJAS_ACTIVAS.items():
        if getattr(c, "estado", "") == "abierta":
            caja_id = cid
            break
    await save_suspended_sale(str(caja_id), payload.id, payload.model_dump(mode="json"))
    return {"mensaje": "Venta pausada exitosamente", "id": payload.id}


@router.get("/ventas/suspendidas", response_model=List[VentaSuspendida])
async def listar_ventas_suspendidas_todas():
    """RF-12: Recuperar lista global de ventas en espera."""
    ventas = await list_suspended_sales()
    return [VentaSuspendida(**venta) for venta in ventas]


@router.delete("/ventas/suspendidas/{id}")
async def reanudar_venta_suspendida_global(id: str):
    """RF-12: Reanudar venta por su ID directo."""
    venta = await get_suspended_sale(id)
    if not venta:
        raise HTTPException(
            status_code=404,
            detail="Venta suspendida no encontrada"
        )
    await delete_suspended_sale(id)
    return venta


# ============================================================================
# HISTORIA KAN-10 / KAN-27: RETIRO EN SUCURSAL CLICK & COLLECT (RF-11)
# SUBTAREAS: KAN-107, KAN-108, KAN-324, KAN-325
# ============================================================================

def _get_supabase_safe() -> Optional[Any]:
    try:
        return get_supabase_admin_client()
    except Exception:
        return None

# Almacén de pedidos Click & Collect para validación rápida en mostrador
_CLICK_AND_COLLECT_DB: Dict[str, Dict[str, Any]] = {
    "RET-789214": {
        "orden_id": uuid.UUID("3b749d44-0db0-4e36-9694-84c1724490f1"),
        "codigo_orden": "ORD-2026-CC101",
        "codigo_retiro": "RET-789214",
        "codigo_qr": "MAXI-CC|ORD-2026-CC101|RET-789214|SUC-01",
        "estado": "confirmada",
        "sucursal_id": "SUC-01",
        "sucursal_nombre": "Sucursal Central - La Paz",
        "fecha_compra": "2026-10-10T09:30:00Z",
        "cliente_nombre": "Carlos Mendoza Patzi",
        "cliente_documento": "4829102",
        "cliente_telefono": "+591 71234567",
        "cliente_email": "carlos.mendoza@gmail.com",
        "subtotal": Decimal("15766.00"),
        "descuento": Decimal("0.0"),
        "total": Decimal("15766.00"),
        "metodo_pago": "QR Simple (Aprobado)",
        "cuf_factura": "CUF-1028374029-20261010-093011-8849",
        "numero_factura": 1421,
        "items": [
            {
                "sku": "LAP-DELL-XPS15",
                "nombre_producto": "Laptop Dell XPS 15 (OLED 4K, i7 13va Gen)",
                "cantidad": 1,
                "precio_unitario": Decimal("6767.00"),
                "total_linea": Decimal("6767.00")
            },
            {
                "sku": "MOU-LOG-MX3S",
                "nombre_producto": "Mouse Inalámbrico Logitech MX Master 3S",
                "cantidad": 1,
                "precio_unitario": Decimal("8999.00"),
                "total_linea": Decimal("8999.00")
            }
        ],
        "despacho": None
    },
    "RET-345091": {
        "orden_id": uuid.UUID("c56b06e9-bfe9-4e7a-9a99-8ee3ad192305"),
        "codigo_orden": "ORD-2026-CC102",
        "codigo_retiro": "RET-345091",
        "codigo_qr": "MAXI-CC|ORD-2026-CC102|RET-345091|SUC-01",
        "estado": "entregada",
        "sucursal_id": "SUC-01",
        "sucursal_nombre": "Sucursal Central - La Paz",
        "fecha_compra": "2026-10-09T16:20:00Z",
        "cliente_nombre": "Sofía Doria Medina",
        "cliente_documento": "6543210",
        "cliente_telefono": "+591 76543210",
        "cliente_email": "sofia.doria@gmail.com",
        "subtotal": Decimal("1850.00"),
        "descuento": Decimal("0.0"),
        "total": Decimal("1850.00"),
        "metodo_pago": "Tarjeta Visa Débito",
        "cuf_factura": "CUF-1028374029-20261009-162100-3321",
        "numero_factura": 1419,
        "items": [
            {
                "sku": "KEY-RGB-01",
                "nombre_producto": "Teclado Mecánico RGB Switches Brown",
                "cantidad": 2,
                "precio_unitario": Decimal("925.00"),
                "total_linea": Decimal("1850.00")
            }
        ],
        "despacho": {
            "fecha_entrega": "2026-10-10T10:15:00Z",
            "cajero_id": "c0000000-0000-0000-0000-000000000002",
            "cajero_nombre": "Oscar Menacho",
            "sucursal_id": "SUC-01",
            "sucursal_nombre": "Sucursal Central - La Paz",
            "receptor_nombre": "Roberto Doria Medina",
            "receptor_documento": "6543211",
            "receptor_tipo": "tercero_autorizado",
            "receptor_telefono": "+591 76543299",
            "observaciones": "Retiro autorizado con fotocopia de CI y carta poder simple.",
            "numero_acta": "ACTA-CC-2026-0041"
        }
    },
    "RET-992381": {
        "orden_id": uuid.UUID("4422e861-55ff-4ab0-b19b-c6b6103e911f"),
        "codigo_orden": "ORD-2026-CC103",
        "codigo_retiro": "RET-992381",
        "codigo_qr": "MAXI-CC|ORD-2026-CC103|RET-992381|SUC-01",
        "estado": "cancelada",
        "sucursal_id": "SUC-01",
        "sucursal_nombre": "Sucursal Central - La Paz",
        "fecha_compra": "2026-10-08T11:00:00Z",
        "cliente_nombre": "Juan Pérez García",
        "cliente_documento": "11223344",
        "cliente_telefono": "+591 79988776",
        "cliente_email": "juan.perez@empresa.bo",
        "subtotal": Decimal("4500.00"),
        "descuento": Decimal("0.0"),
        "total": Decimal("4500.00"),
        "metodo_pago": "QR Simple",
        "cuf_factura": None,
        "numero_factura": None,
        "items": [
            {
                "sku": "MON-4K-27",
                "nombre_producto": "Monitor Profesional 27 Pulgadas 4K",
                "cantidad": 1,
                "precio_unitario": Decimal("4500.00"),
                "total_linea": Decimal("4500.00")
            }
        ],
        "despacho": None
    }
}


def _extraer_codigo_clave(codigo_raw: str) -> str:
    """Extrae el código de retiro o código de orden desde texto, QR o prefijo."""
    val = codigo_raw.strip()
    if "|" in val:
        # Formato de QR: MAXI-CC|ORD-XXXX|RET-XXXX|SUC-XX
        partes = val.split("|")
        for p in partes:
            if p.startswith("RET-"):
                return p
        for p in partes:
            if p.startswith("ORD-"):
                return p
    return val.upper()


@router.get("/click-and-collect/pedidos", response_model=List[PedidoRetiroResponse])
async def listar_pedidos_click_and_collect(
    sucursal_id: Optional[str] = None,
    filtro_estado: Optional[str] = None
):
    """KAN-324: Listar pedidos Click & Collect para la pantalla de mostrador."""
    resultados = []
    
    # 1. Obtener desde el almacén de memoria
    for record in _CLICK_AND_COLLECT_DB.values():
        if sucursal_id and record.get("sucursal_id") and record["sucursal_id"] != sucursal_id:
            continue
        
        estado = record["estado"]
        if filtro_estado:
            if filtro_estado == "pendientes" and estado not in ("confirmada", "en_preparacion", "despachada", "pendiente_retiro"):
                continue
            elif filtro_estado == "entregados" and estado != "entregada":
                continue

        es_entregable = estado in ("confirmada", "en_preparacion", "despachada", "pendiente_retiro")
        motivo = None
        if estado == "entregada":
            desp = record.get("despacho")
            if desp:
                motivo = f"Pedido entregado el {desp.get('fecha_entrega', '')} a {desp.get('receptor_nombre', 'el titular')}"
            else:
                motivo = "El pedido ya figura como entregado previamente."
        elif estado == "cancelada":
            motivo = "El pedido fue cancelado y no puede ser despachado."

        resultados.append(PedidoRetiroResponse(
            orden_id=record["orden_id"],
            codigo_orden=record["codigo_orden"],
            codigo_retiro=record["codigo_retiro"],
            codigo_qr=record.get("codigo_qr"),
            estado=estado,
            es_entregable=es_entregable,
            motivo_rechazo=motivo,
            sucursal_id=record.get("sucursal_id"),
            sucursal_nombre=record.get("sucursal_nombre", "Sucursal Central"),
            fecha_compra=record["fecha_compra"],
            cliente_nombre=record["cliente_nombre"],
            cliente_documento=record["cliente_documento"],
            cliente_telefono=record.get("cliente_telefono"),
            cliente_email=record.get("cliente_email"),
            subtotal=record["subtotal"],
            descuento=record.get("descuento", Decimal("0.0")),
            total=record["total"],
            metodo_pago=record.get("metodo_pago"),
            cuf_factura=record.get("cuf_factura"),
            numero_factura=record.get("numero_factura"),
            items=[DetalleItemRetiro(**i) for i in record["items"]],
            despacho=AuditoriaDespachoInfo(**record["despacho"]) if record.get("despacho") else None
        ))

    return resultados


@router.post("/click-and-collect/validar", response_model=PedidoRetiroResponse)
async def validar_codigo_click_and_collect(payload: ValidarRetiroRequest):
    """
    KAN-324: [BE] Endpoint para validación de código o QR de retiro Click & Collect.
    KAN-108: Validación de identidad y estado del pedido.
    """
    codigo_busqueda = _extraer_codigo_clave(payload.codigo)
    
    # 1. Buscar coincidencia exacta por código de retiro o código de orden
    record = None
    for r in _CLICK_AND_COLLECT_DB.values():
        if (
            r["codigo_retiro"].upper() == codigo_busqueda or
            r["codigo_orden"].upper() == codigo_busqueda or
            str(r["orden_id"]).upper() == codigo_busqueda or
            r["cliente_documento"] == codigo_busqueda
        ):
            record = r
            break

    # 2. Si no está en memoria, consultar en Supabase
    if not record:
        client = _get_supabase_safe()
        if client:
            try:
                res = client.table("ordenes").select("*, orden_items(*), perfiles_clientes(*)").or_(
                    f"codigo_orden.ilike.%{codigo_busqueda}%,cuf_factura.ilike.%{codigo_busqueda}%"
                ).limit(1).execute()
                if res.data:
                    row = res.data[0]
                    cli = row.get("perfiles_clientes") or {}
                    items_raw = row.get("orden_items") or []
                    cod_retiro = f"RET-{row['codigo_orden'].replace('ORD-', '')[:6]}"
                    record = {
                        "orden_id": uuid.UUID(row["id"]),
                        "codigo_orden": row["codigo_orden"],
                        "codigo_retiro": cod_retiro,
                        "codigo_qr": f"MAXI-CC|{row['codigo_orden']}|{cod_retiro}|SUC-01",
                        "estado": row.get("estado", "confirmada"),
                        "sucursal_id": payload.sucursal_id or "SUC-01",
                        "sucursal_nombre": "Sucursal Central - La Paz",
                        "fecha_compra": row.get("created_at", datetime.utcnow().isoformat()),
                        "cliente_nombre": cli.get("razon_social") or cli.get("nombre_completo", "Cliente Mostrador"),
                        "cliente_documento": cli.get("nit_ci", "0"),
                        "cliente_telefono": cli.get("telefono"),
                        "cliente_email": cli.get("email"),
                        "subtotal": Decimal(str(row.get("subtotal", 0))),
                        "descuento": Decimal(str(row.get("descuento", 0))),
                        "total": Decimal(str(row.get("total", 0))),
                        "metodo_pago": "Aprobado",
                        "cuf_factura": row.get("cuf_factura"),
                        "numero_factura": None,
                        "items": [
                            {
                                "sku": it.get("sku", "ITEM"),
                                "nombre_producto": it.get("nombre_producto", "Producto"),
                                "cantidad": it.get("cantidad", 1),
                                "precio_unitario": Decimal(str(it.get("precio_unitario", 0))),
                                "total_linea": Decimal(str(it.get("total_linea", 0)))
                            }
                            for it in items_raw
                        ],
                        "despacho": None
                    }
                    _CLICK_AND_COLLECT_DB[cod_retiro] = record
            except Exception:
                pass

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró ningún pedido Click & Collect con el código o QR '{payload.codigo}'."
        )

    # Evaluación de estado y entregabilidad (KAN-108)
    estado = record["estado"]
    es_entregable = estado in ("confirmada", "en_preparacion", "despachada", "pendiente_retiro")
    motivo_rechazo = None

    if estado == "entregada":
        desp = record.get("despacho")
        if desp:
            motivo_rechazo = (
                f"Este pedido YA FUE ENTREGADO previamente el {desp.get('fecha_entrega')} "
                f"al receptor {desp.get('receptor_nombre')} (Doc: {desp.get('receptor_documento')}) "
                f"por el Cajero {desp.get('cajero_nombre')}."
            )
        else:
            motivo_rechazo = "El pedido ya figura registrado en estado ENTREGADO."
    elif estado == "cancelada":
        motivo_rechazo = "El pedido se encuentra CANCELADO. Las existencias fueron restituidas a almacén."

    return PedidoRetiroResponse(
        orden_id=record["orden_id"],
        codigo_orden=record["codigo_orden"],
        codigo_retiro=record["codigo_retiro"],
        codigo_qr=record.get("codigo_qr"),
        estado=estado,
        es_entregable=es_entregable,
        motivo_rechazo=motivo_rechazo,
        sucursal_id=record.get("sucursal_id"),
        sucursal_nombre=record.get("sucursal_nombre", "Sucursal Central"),
        fecha_compra=record["fecha_compra"],
        cliente_nombre=record["cliente_nombre"],
        cliente_documento=record["cliente_documento"],
        cliente_telefono=record.get("cliente_telefono"),
        cliente_email=record.get("cliente_email"),
        subtotal=record["subtotal"],
        descuento=record.get("descuento", Decimal("0.0")),
        total=record["total"],
        metodo_pago=record.get("metodo_pago"),
        cuf_factura=record.get("cuf_factura"),
        numero_factura=record.get("numero_factura"),
        items=[DetalleItemRetiro(**i) for i in record["items"]],
        despacho=AuditoriaDespachoInfo(**record["despacho"]) if record.get("despacho") else None
    )


@router.post("/click-and-collect/confirmar-entrega", response_model=ConfirmarEntregaResponse)
@require_jwt_claims("sub", allowed_roles={"cajero", "administrador"})
async def confirmar_entrega_click_and_collect(
    payload: ConfirmarEntregaRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    KAN-325: [BE] Lógica de actualización de pedido a 'Entregado' y auditoría de despacho (RF-11, RF-50).
    Registra el acta de entrega y datos del receptor (titular o tercero autorizado).
    """
    clave = _extraer_codigo_clave(payload.codigo_retiro)
    record = None
    
    for r in _CLICK_AND_COLLECT_DB.values():
        if (
            r["codigo_retiro"].upper() == clave or
            r["orden_id"] == payload.orden_id or
            r["codigo_orden"].upper() == clave
        ):
            record = r
            break

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pedido no encontrado para confirmación de entrega."
        )

    # Validar que el pedido esté en un estado entregable
    if record["estado"] == "entregada":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Operación inválida: El pedido ya fue entregado con anterioridad."
        )
    if record["estado"] == "cancelada":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Operación inválida: El pedido se encuentra cancelado."
        )

    ahora_iso = datetime.utcnow().isoformat()
    correlativo_acta = f"ACTA-CC-{datetime.utcnow().year}-{str(uuid.uuid4().hex[:6]).upper()}"

    # Construir auditoría inmutable de despacho (RF-50)
    auditoria = {
        "fecha_entrega": ahora_iso,
        "cajero_id": payload.cajero_id or current_user.get("sub", "cajero-pos"),
        "cajero_nombre": payload.cajero_nombre or "Cajero Central (Turno Activo)",
        "sucursal_id": payload.sucursal_id or record.get("sucursal_id", "SUC-01"),
        "sucursal_nombre": payload.sucursal_nombre or record.get("sucursal_nombre", "Sucursal Central - La Paz"),
        "receptor_nombre": payload.receptor_nombre.strip(),
        "receptor_documento": payload.receptor_documento.strip(),
        "receptor_tipo": payload.receptor_tipo,
        "receptor_telefono": payload.receptor_telefono,
        "observaciones": payload.observaciones,
        "numero_acta": correlativo_acta
    }

    # Actualizar estado atómico en memoria
    record["estado"] = "entregada"
    record["despacho"] = auditoria

    # Persistir cambio en Supabase
    client = _get_supabase_safe()
    if client:
        try:
            client.table("ordenes").update({
                "estado": "entregada",
                "updated_at": ahora_iso
            }).eq("id", str(record["orden_id"])).execute()

            # Registrar log de auditoría (RF-50)
            client.table("audit_logs").insert({
                "usuario_id": payload.cajero_id or current_user.get("sub"),
                "accion": "DESPACHO_CLICK_AND_COLLECT",
                "entidad": "ordenes",
                "entidad_id": str(record["orden_id"]),
                "datos_previos": {"estado": "confirmada"},
                "datos_nuevos": {
                    "estado": "entregada",
                    "despacho": auditoria
                }
            }).execute()
        except Exception:
            pass

    comprobante = {
        "acta_numero": correlativo_acta,
        "codigo_orden": record["codigo_orden"],
        "codigo_retiro": record["codigo_retiro"],
        "titular": record["cliente_nombre"],
        "receptor": payload.receptor_nombre,
        "documento_receptor": payload.receptor_documento,
        "tipo_receptor": payload.receptor_tipo,
        "cajero": auditoria["cajero_nombre"],
        "sucursal": auditoria["sucursal_nombre"],
        "fecha": ahora_iso,
        "total_items": sum(i["cantidad"] for i in record["items"]),
        "monto_total": float(record["total"])
    }

    return ConfirmarEntregaResponse(
        success=True,
        orden_id=record["orden_id"],
        codigo_orden=record["codigo_orden"],
        codigo_retiro=record["codigo_retiro"],
        nuevo_estado="entregada",
        fecha_entrega=ahora_iso,
        receptor_nombre=payload.receptor_nombre,
        receptor_documento=payload.receptor_documento,
        receptor_tipo=payload.receptor_tipo,
        cajero_nombre=auditoria["cajero_nombre"],
        comprobante_entrega=comprobante,
        mensaje="Pedido Click & Collect entregado exitosamente y auditoría de despacho registrada."
    )


# Compatibilidad retroactiva con endpoint simple
@router.post("/pedidos/retiro-sucursal/validar")
async def validar_retiro_sucursal_legacy(codigo_retiro: str):
    """RF-11: Validar entrega de pedido Click & Collect (compatibilidad)."""
    clave = _extraer_codigo_clave(codigo_retiro)
    if clave in _CLICK_AND_COLLECT_DB:
        _CLICK_AND_COLLECT_DB[clave]["estado"] = "entregada"
    return {
        "codigo_retiro": codigo_retiro,
        "estado": "ENTREGADO",
        "mensaje": "Pedido entregado presencialmente con éxito"
    }
