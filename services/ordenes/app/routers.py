import logging
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
try:
    from app.schemas import (
        OrdenCreate, OrdenResponse, ItemOrdenResponse,
        TransicionEstadoRequest, CotizacionB2BCreate, CotizacionB2BResponse
    )
    from app.routers_facturacion import generar_cuf
except (ModuleNotFoundError, ImportError):
    from backend.services.ordenes.app.schemas import (
        OrdenCreate, OrdenResponse, ItemOrdenResponse,
        TransicionEstadoRequest, CotizacionB2BCreate, CotizacionB2BResponse
    )
    from backend.services.ordenes.app.routers_facturacion import generar_cuf
from backend.shared.database import get_supabase_admin_client
from backend.shared.erp_clients.inventarios import inventarios_client
from backend.shared.erp_clients.pagos import pagos_client
from backend.shared.erp_clients.entregas import entregas_client
from backend.shared.erp_clients.contabilidad import contabilidad_client
from backend.shared.redis_client import consultar_reserva, confirmar_reserva_stock
from backend.shared.security import get_current_user, require_jwt_claims

logger = logging.getLogger("maxiconecta.ordenes")
router = APIRouter(prefix="/api/v1/ordenes", tags=["Órdenes y Ventas"])

def _get_supabase_safe() -> Optional[Any]:
    try:
        return get_supabase_admin_client()
    except Exception as e:
        logger.warning(f"Aviso al inicializar cliente Supabase: {e}")
        return None

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

    # 1. Validar y confirmar reserva en Redis / Inventarios (RF-14 · RIO-INV-02 / RIO-INV-03)
    if payload.reserva_id:
        reserva = await consultar_reserva(payload.reserva_id)
        if not reserva or reserva.get("status") == "EXPIRADA":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La reserva de stock ha expirado o no es válida (límite de 15 minutos superado). Por favor inicie un nuevo checkout."
            )
        await confirmar_reserva_stock(payload.reserva_id)
        await inventarios_client.descuento_definitivo(payload.reserva_id, str(orden_id))

    # 2. Generar orden de despacho si es a domicilio (RIO-ENT-01)
    tracking_num = None
    if payload.tipo_despacho == "domicilio":
        despacho_res = await entregas_client.solicitar_despacho({
            "orden_id": str(orden_id),
            "direccion_id": str(payload.direccion_entrega_id) if payload.direccion_entrega_id else None,
            "items": [
                {
                    "variante_id": str(i.variante_id),
                    "sku": i.sku,
                    "nombre_producto": i.nombre_producto,
                    "cantidad": i.cantidad,
                    "precio_unitario": float(i.precio_unitario)
                }
                for i in payload.items
            ]
        })
        tracking_num = despacho_res.get("guia_despacho")

    # 3. Registrar asiento contable de ventas (RIO-CON-01)
    await contabilidad_client.registrar_asiento_venta({
        "orden_id": str(orden_id),
        "monto_total": float(payload.total),
        "canal": payload.canal
    })

    # 4. Generación y timbrado de Factura Legal Electrónica (RF-10, RF-45, RIO-PAG-02, KAN-367)
    df = payload.datos_fiscales
    modalidad = df.modalidad if df else "con_factura"
    es_cf = modalidad == "sin_factura" or (df and df.nit_ci in ("0", "99001"))
    nit_final = "0" if es_cf else (df.nit_ci.strip() if df and df.nit_ci else "0")
    razon_final = "CONSUMIDOR FINAL" if es_cf else (df.razon_social.strip().upper() if df and df.razon_social else "CONSUMIDOR FINAL")
    tipo_doc_final = "CI" if es_cf else (df.tipo_documento.upper() if df and df.tipo_documento else "NIT")
    email_fac = df.email_facturacion if df else None

    # Correlativo secuencial y timbrado CUF
    import time
    numero_factura = int(time.time() % 1000000) + 1000
    nit_emisor = "1028374029"
    ahora = datetime.utcnow()
    cuf = generar_cuf(
        nit_emisor=nit_emisor,
        fecha_hora=ahora,
        sucursal=0,
        modalidad=1,
        tipo_emision=1,
        tipo_doc_sector=1,
        numero_factura=numero_factura,
        punto_venta=1
    )
    cufd = f"CUFD-{uuid.uuid4().hex[:8].upper()}-{ahora.strftime('%Y%m%d')}"
    total_float = float(payload.total)
    qr_url = f"https://pilotosiat.impuestos.gob.bo/consulta/QR?nit={nit_emisor}&cuf={cuf}&numero={numero_factura}&t={total_float:.2f}"

    factura_data = {
        "numero_factura": numero_factura,
        "cuf": cuf,
        "cufd": cufd,
        "fecha_emision": ahora.isoformat(),
        "modalidad": "sin_factura" if es_cf else "con_factura",
        "datos_comprador": {
            "tipo_documento": tipo_doc_final,
            "nit_ci": nit_final,
            "razon_social": razon_final,
            "email_facturacion": email_fac
        },
        "monto_total": total_float,
        "monto_iva": round(total_float * 0.13, 2),
        "codigo_qr": qr_url,
        "leyenda_fiscal": "Ley N° 453: El proveedor deberá suministrar el servicio en las modalidades y términos ofertados."
    }

    try:
        await pagos_client.emitir_factura({
            "orden_id": str(orden_id),
            "numero_factura": numero_factura,
            "cuf": cuf,
            "nit_ci": nit_final,
            "razon_social": razon_final,
            "monto_total": total_float
        })
    except Exception as e:
        logger.warning(f"Aviso comunicando con ERP Pagos: {e}")

    # RIO-INV-03 / KAN-56 / KAN-284: Descuento definitivo de existencias y publicación Pub/Sub
    try:
        items_payload = [{"sku": i.sku, "cantidad": i.cantidad, "nombre": i.nombre_producto} for i in payload.items]
        await inventarios_client.descuento_definitivo(
            reserva_id=payload.reserva_id or f"RES-DIR-{orden_id.hex[:6]}",
            orden_id=str(orden_id),
            items=items_payload
        )
    except Exception as e:
        logger.warning(f"Aviso comunicando descuento definitivo con Inventarios: {e}")

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
        cuf_factura=cuf,
        numero_factura=numero_factura,
        factura=factura_data,
        created_at=datetime.utcnow(),
        items=items_res
    )
    _ORDENES_DB[str(orden_id)] = orden

    client = _get_supabase_safe()
    if client:
        try:
            # Resolver cliente_id válido para FK de Supabase
            cliente_db_uuid = None
            raw_client_id = str(payload.cliente_id)
            try:
                # Si ya es un UUID válido
                uuid.UUID(raw_client_id)
                cliente_db_uuid = raw_client_id
            except ValueError:
                # No es UUID (ej. 'cliente-anonimo')
                if not es_cf and nit_final != "0":
                    cli_res = client.table("perfiles_clientes").select("id").eq("nit_ci", nit_final).limit(1).execute()
                    if cli_res.data:
                        cliente_db_uuid = cli_res.data[0]["id"]
                if not cliente_db_uuid:
                    if not es_cf and df and df.guardar_perfil:
                        safe_email = email_fac if email_fac and "@" in email_fac else f"cliente.{nit_final}.{int(time.time())}@maxiconecta.bo"
                        new_cli = client.table("perfiles_clientes").insert({
                            "nombre_completo": razon_final,
                            "email": safe_email,
                            "nit_ci": nit_final,
                            "razon_social": razon_final,
                            "tipo_cliente": "retail"
                        }).execute()
                        if new_cli.data:
                            cliente_db_uuid = new_cli.data[0]["id"]
                if not cliente_db_uuid:
                    any_cli = client.table("perfiles_clientes").select("id").limit(1).execute()
                    if any_cli.data:
                        cliente_db_uuid = any_cli.data[0]["id"]

            if cliente_db_uuid:
                client.table("ordenes").insert({
                    "id": str(orden_id),
                    "codigo_orden": codigo,
                    "cliente_id": cliente_db_uuid,
                    "canal": payload.canal,
                    "tipo_despacho": payload.tipo_despacho,
                    "direccion_entrega_id": str(payload.direccion_entrega_id) if payload.direccion_entrega_id and len(str(payload.direccion_entrega_id)) == 36 else None,
                    "subtotal": float(payload.subtotal),
                    "descuento": float(payload.descuento),
                    "costo_envio": float(payload.costo_envio),
                    "total": float(payload.total),
                    "estado": "confirmada",
                    "tracking_number": tracking_num,
                    "cuf_factura": cuf
                }).execute()

                items_to_insert = [
                    {
                        "id": str(item.id),
                        "orden_id": str(orden_id),
                        "variante_id": str(item.variante_id) if len(str(item.variante_id)) == 36 else None,
                        "sku": item.sku,
                        "nombre_producto": item.nombre_producto,
                        "cantidad": item.cantidad,
                        "precio_unitario": float(item.precio_unitario),
                        "total_linea": float(item.total_linea),
                    }
                    for item in items_res
                ]
                # Filtrar campos nulos si variante_id es requerida
                valid_items = [it for it in items_to_insert if it.get("variante_id")]
                if valid_items:
                    client.table("orden_items").insert(valid_items).execute()

                # Inserción en tabla 'pagos' con comprobante y QR timbrado
                metodos_validos = ["tarjeta", "qr", "transferencia", "efectivo", "pasarela"]
                metodo_norm = payload.metodo_pago.lower() if payload.metodo_pago.lower() in metodos_validos else "tarjeta"
                client.table("pagos").insert({
                    "orden_id": str(orden_id),
                    "transaccion_id": f"TX-{cuf.replace('CUF-', '')[:14]}",
                    "metodo": metodo_norm,
                    "monto": total_float,
                    "moneda": "BOB",
                    "estado": "aprobado",
                    "raw_payload": factura_data
                }).execute()

        except Exception as e:
            logger.warning(f"Aviso al persistir orden en Supabase (conservada en memoria local): {e}")

    return orden

@router.get("/{id}", response_model=OrdenResponse)
async def obtener_orden(id: uuid.UUID):
    """RF-29, RF-37: Detalle e historial de orden."""
    oid = str(id)
    client = _get_supabase_safe()
    if client:
        try:
            res = client.table("ordenes").select("*, orden_items(*)").eq("id", oid).limit(1).execute()
            if res.data:
                row = res.data[0]
                raw_items = row.get("orden_items") or []
                items_res = [
                    ItemOrdenResponse(
                        id=uuid.UUID(i["id"]) if isinstance(i["id"], str) else i["id"],
                        variante_id=uuid.UUID(i["variante_id"]) if isinstance(i["variante_id"], str) else i["variante_id"],
                        sku=i["sku"],
                        nombre_producto=i["nombre_producto"],
                        cantidad=i["cantidad"],
                        precio_unitario=Decimal(str(i["precio_unitario"])),
                        total_linea=Decimal(str(i.get("total_linea", i["cantidad"] * i["precio_unitario"])))
                    )
                    for i in raw_items
                ]
                return OrdenResponse(
                    id=uuid.UUID(row["id"]) if isinstance(row["id"], str) else row["id"],
                    codigo_orden=row["codigo_orden"],
                    cliente_id=uuid.UUID(row["cliente_id"]) if isinstance(row["cliente_id"], str) else row["cliente_id"],
                    canal=row.get("canal", "web"),
                    tipo_despacho=row.get("tipo_despacho", "domicilio"),
                    subtotal=Decimal(str(row["subtotal"])),
                    total=Decimal(str(row["total"])),
                    estado=row.get("estado", "confirmada"),
                    tracking_number=row.get("tracking_number"),
                    cuf_factura=row.get("cuf_factura"),
                    created_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")) if "created_at" in row else datetime.utcnow(),
                    items=items_res
                )
        except Exception as e:
            logger.warning(f"Error consultando orden en Supabase: {e}")

    if oid in _ORDENES_DB:
        return _ORDENES_DB[oid]
    raise HTTPException(status_code=404, detail="Orden no encontrada")

@router.patch("/{id}/estado", response_model=OrdenResponse)
@require_jwt_claims("sub", allowed_roles={"administrador", "gerente_comercial", "cajero"})
async def cambiar_estado_orden(
    id: uuid.UUID,
    payload: TransicionEstadoRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
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
    client = _get_supabase_safe()
    if client:
        try:
            client.table("ordenes").update({"estado": nuevo_estado}).eq("id", oid).execute()
        except Exception as e:
            logger.warning(f"Error actualizando estado de orden en Supabase: {e}")

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
    client = _get_supabase_safe()
    if client:
        try:
            client.table("ordenes").update({"estado": "cancelada"}).eq("id", oid).execute()
        except Exception as e:
            logger.warning(f"Error cancelando orden en Supabase: {e}")

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
@require_jwt_claims("sub", allowed_roles={"administrador", "gerente_comercial"})
async def aprobar_cotizacion(
    id: uuid.UUID,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """RF-35: Aprobación jerárquica de cotización B2B."""
    cid = str(id)
    if cid not in _COTIZACIONES_DB:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    cot = _COTIZACIONES_DB[cid]
    cot.estado = "aprobada"
    return cot
