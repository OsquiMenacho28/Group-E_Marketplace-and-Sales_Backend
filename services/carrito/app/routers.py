import uuid
import time
from decimal import Decimal
from fastapi import APIRouter, HTTPException, status
from typing import List
try:
    from app.schemas import (
        ItemCarritoAdd, ItemCarritoResponse, ItemCarritoUpdate, CarritoResponse,
        AplicarCuponRequest, CheckoutInitRequest, CheckoutInitResponse,
        ReservaConsultaResponse, CancelarReservaResponse,
        WishlistAdd, WishlistResponse
    )
    from app import cupones_store
    from app.cupones_engine import evaluar_cupon
except (ModuleNotFoundError, ImportError):
    from backend.services.carrito.app.schemas import (
        ItemCarritoAdd, ItemCarritoResponse, ItemCarritoUpdate, CarritoResponse,
        AplicarCuponRequest, CheckoutInitRequest, CheckoutInitResponse,
        ReservaConsultaResponse, CancelarReservaResponse,
        WishlistAdd, WishlistResponse
    )
    from backend.services.carrito.app import cupones_store
    from backend.services.carrito.app.cupones_engine import evaluar_cupon
from backend.shared.redis_client import (
    get_cart_from_cache, save_cart_to_cache, delete_cart_from_cache,
    lock_stock_reservation, crear_reserva_stock, consultar_reserva,
    liberar_reserva_stock, confirmar_reserva_stock
)
from backend.shared.erp_clients.inventarios import inventarios_client
from backend.shared import stock_ledger

from backend.shared.database import get_supabase_client

router = APIRouter(prefix="/api/v1/carrito", tags=["Carrito y Checkout"])

async def _descuento_vigente(raw: dict, subtotal: Decimal) -> Decimal:
    """
    RF-17: recalcula el descuento del cupón guardado en el carrito contra el
    subtotal actual (si se quitan ítems y ya no se cumple el monto mínimo, o el
    cupón venció/se desactivó, el descuento deja de aplicarse).
    """
    codigo = raw.get("cupon")
    if not codigo:
        return Decimal("0.0")
    resultado = evaluar_cupon(await cupones_store.obtener(codigo), subtotal, codigo_solicitado=codigo)
    return resultado.descuento if resultado.valido else Decimal("0.0")


async def _validar_stock_carrito(items: List[dict], sku: str) -> None:
    total = sum(int(item["cantidad"]) for item in items if item.get("sku") == sku)
    disponible = await stock_ledger.available_stock(sku, register_missing=False)
    if disponible is not None and total > disponible:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Stock insuficiente para {sku}. Disponibles: {disponible}."
        )

@router.get("/{identificador}", response_model=CarritoResponse)
async def ver_carrito(identificador: str):
    """RF-13: Obtener carrito persistente desde Redis."""
    raw = await get_cart_from_cache(identificador)
    items = [
        ItemCarritoResponse(
            variante_id=i["variante_id"],
            sku=i["sku"],
            nombre=i["nombre"],
            cantidad=i["cantidad"],
            precio_unitario=Decimal(str(i["precio_unitario"])),
            total_linea=Decimal(str(i["cantidad"])) * Decimal(str(i["precio_unitario"]))
        ) for i in raw.get("items", [])
    ]
    subtotal = sum(i.total_linea for i in items)
    descuento = await _descuento_vigente(raw, subtotal)
    return CarritoResponse(
        cliente_o_sesion_id=identificador,
        items=items,
        subtotal=subtotal,
        descuento_cupon=descuento,
        cupon_codigo=raw.get("cupon"),
        total=max(Decimal("0.0"), subtotal - descuento)
    )

@router.post("/{identificador}/items", response_model=CarritoResponse)
async def agregar_item_carrito(identificador: str, payload: ItemCarritoAdd):
    """RF-13: Agregar o actualizar ítem en el carrito."""
    raw = await get_cart_from_cache(identificador)
    items = raw.get("items", [])

    # Buscar si ya existe
    encontrado = False
    for i in items:
        if i["variante_id"] == str(payload.variante_id):
            i["cantidad"] += payload.cantidad
            encontrado = True
            break

    if not encontrado:
        items.append({
            "variante_id": str(payload.variante_id),
            "sku": payload.sku,
            "nombre": payload.nombre,
            "cantidad": payload.cantidad,
            "precio_unitario": float(payload.precio_unitario)
        })

    raw["items"] = items
    await _validar_stock_carrito(items, payload.sku)
    await save_cart_to_cache(identificador, raw)
    return await ver_carrito(identificador)

@router.delete("/{identificador}/items/{variante_id}", response_model=CarritoResponse)
async def remover_item_carrito(identificador: str, variante_id: str):
    """RF-13: Quitar ítem del carrito."""
    raw = await get_cart_from_cache(identificador)
    raw["items"] = [i for i in raw.get("items", []) if i["variante_id"] != variante_id]
    await save_cart_to_cache(identificador, raw)
    return await ver_carrito(identificador)

@router.put("/{identificador}/items/{variante_id}", response_model=CarritoResponse)
async def actualizar_cantidad_item(identificador: str, variante_id: str, payload: ItemCarritoUpdate):
    """Actualiza una cantidad persistida en Redis."""
    raw = await get_cart_from_cache(identificador)
    item = next((entry for entry in raw.get("items", []) if entry["variante_id"] == variante_id), None)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El ítem no existe en el carrito")
    item["cantidad"] = payload.cantidad
    await _validar_stock_carrito(raw.get("items", []), item["sku"])
    await save_cart_to_cache(identificador, raw)
    return await ver_carrito(identificador)

@router.post("/{identificador}/cupon", response_model=CarritoResponse)
async def aplicar_cupon(identificador: str, payload: AplicarCuponRequest):
    """RF-17: Validar (vigencia, monto mínimo, límite de canjes) y aplicar cupón de descuento."""
    codigo = payload.codigo.strip().upper()
    raw = await get_cart_from_cache(identificador)
    subtotal = sum(Decimal(str(item["cantidad"])) * Decimal(str(item["precio_unitario"])) for item in raw.get("items", []))
    resultado = evaluar_cupon(await cupones_store.obtener(codigo), subtotal, codigo_solicitado=codigo)
    if not resultado.valido:
        raise HTTPException(status_code=400, detail=resultado.mensaje)

    raw["cupon"] = resultado.codigo
    raw["descuento"] = float(resultado.descuento)
    await save_cart_to_cache(identificador, raw)
    return await ver_carrito(identificador)

@router.delete("/{identificador}/cupon", response_model=CarritoResponse)
async def quitar_cupon(identificador: str):
    """RF-17: Quitar el cupón aplicado al carrito."""
    raw = await get_cart_from_cache(identificador)
    raw.pop("cupon", None)
    raw.pop("descuento", None)
    await save_cart_to_cache(identificador, raw)
    return await ver_carrito(identificador)

@router.post("/{identificador}/checkout/iniciar", response_model=CheckoutInitResponse)
async def iniciar_checkout(identificador: str, payload: CheckoutInitRequest):
    """RF-14, RIO-INV-02: Bloqueo temporal de stock en Redis por 15 minutos (900s)."""
    raw = await get_cart_from_cache(identificador)
    items = raw.get("items", [])
    if not items:
        raise HTTPException(status_code=400, detail="El carrito está vacío")

    # 1. Solicitar reserva formal al ERP de Inventarios (RIO-INV-02)
    erp_res = await inventarios_client.reservar_stock(items, ttl_segundos=900)
    if erp_res.get("status") == "RECHAZADA":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=erp_res.get("mensaje", "Stock insuficiente en almacén para completar la reserva.")
        )

    reserva_id = erp_res.get("reserva_id") or f"RES-{uuid.uuid4().hex[:8].upper()}"

    # 2. Bloquear variantes y registrar la reserva estructurada en Redis con TTL de 900s
    await crear_reserva_stock(
        reserva_id=reserva_id,
        cliente_id=str(payload.cliente_id),
        items=items,
        ttl_seconds=900
    )

    items_response = [
        ItemCarritoResponse(
            variante_id=i["variante_id"],
            sku=i["sku"],
            nombre=i["nombre"],
            cantidad=i["cantidad"],
            precio_unitario=Decimal(str(i["precio_unitario"])),
            total_linea=Decimal(str(i["cantidad"])) * Decimal(str(i["precio_unitario"]))
        ) for i in items
    ]

    subtotal = sum(i.total_linea for i in items_response)
    descuento = await _descuento_vigente(raw, subtotal)
    total = max(Decimal("0.0"), subtotal - descuento)

    return CheckoutInitResponse(
        reserva_id=reserva_id,
        ttl_expira_en_segundos=900,
        expira_en_timestamp=time.time() + 900,
        monto_total=total,
        metodo_pago=payload.metodo_pago,
        status="RESERVA_CONFIRMADA",
        items_reservados=items_response
    )

@router.get("/checkout/reserva/{reserva_id}", response_model=ReservaConsultaResponse)
async def consultar_reserva_checkout(reserva_id: str):
    """RF-14: Consultar el estado y tiempo restante (TTL) de una reserva en Redis."""
    reserva = await consultar_reserva(reserva_id)
    if not reserva:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La reserva no existe o ya ha expirado."
        )

    items = reserva.get("items", [])
    subtotal = sum(Decimal(str(i.get("cantidad", 1))) * Decimal(str(i.get("precio_unitario", 0))) for i in items)

    return ReservaConsultaResponse(
        reserva_id=reserva_id,
        segundos_restantes=reserva.get("segundos_restantes", 0),
        estado=reserva.get("status", "ACTIVA"),
        items=items,
        monto_total=subtotal
    )

@router.post("/checkout/reserva/{reserva_id}/cancelar", response_model=CancelarReservaResponse)
async def cancelar_reserva_checkout(reserva_id: str):
    """RF-14, RIO-INV-02: Liberar inmediatamente la reserva si el usuario cancela o abandona el checkout."""
    reserva = await consultar_reserva(reserva_id)
    items = reserva.get("items", []) if reserva else []

    # 1. Notificar al ERP de Inventarios la liberación
    await inventarios_client.liberar_reserva(reserva_id, items)

    # 2. Liberar claves y locks en Redis
    await liberar_reserva_stock(reserva_id)

    return CancelarReservaResponse(
        reserva_id=reserva_id,
        status="RESERVA_CANCELADA",
        mensaje="Reserva liberada exitosamente en Inventarios y Redis"
    )

@router.post(
    "/{cliente_id}/deseos",
    response_model=WishlistResponse,
    status_code=status.HTTP_201_CREATED
)
async def agregar_deseo(cliente_id: uuid.UUID, payload: WishlistAdd):
    """RF-21: Agregar una variante a la lista de deseos."""
    supabase = get_supabase_client()
    if supabase is None:
        raise HTTPException(
            status_code=503,
            detail="Servicio de base de datos no disponible"
        )

    try:
        # Verificar si ya existe previamente para no fallar por unique constraint
        existente = (
            supabase
            .table("deseos")
            .select("*")
            .eq("cliente_id", str(cliente_id))
            .eq("variante_id", str(payload.variante_id))
            .execute()
        )
        if existente.data and len(existente.data) > 0:
            return existente.data[0]

        response = (
            supabase
            .table("deseos")
            .insert({
                "cliente_id": str(cliente_id),
                "variante_id": str(payload.variante_id)
            })
            .execute()
        )

        if not response.data:
            raise HTTPException(
                status_code=400,
                detail="No se pudo agregar el producto a la lista de deseos"
            )

        return response.data[0]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"No se pudo agregar el deseo: {str(e)}"
        )

@router.get(
    "/{cliente_id}/deseos",
    response_model=List[WishlistResponse]
)
async def listar_deseos(cliente_id: uuid.UUID):
    """RF-21: Consultar la lista de deseos del cliente enriquecida con datos del producto."""
    supabase = get_supabase_client()
    if supabase is None:
        raise HTTPException(
            status_code=503,
            detail="Servicio de base de datos no disponible"
        )

    try:
        # Intenta consulta con JOIN a variantes y productos
        response = (
            supabase
            .table("deseos")
            .select("*, variantes(id, sku, nombre_variante, precio, productos(id, nombre, imagenes_producto(url, es_principal)))")
            .eq("cliente_id", str(cliente_id))
            .order("created_at", desc=True)
            .execute()
        )
        items = []
        for row in (response.data or []):
            var_data = row.get("variantes") or {}
            prod_data = var_data.get("productos") or {}
            imgs = prod_data.get("imagenes_producto") or []
            main_img = next((img["url"] for img in imgs if img.get("es_principal")), (imgs[0]["url"] if imgs else None))
            nombre = prod_data.get("nombre") or var_data.get("nombre_variante") or "Producto sin nombre"
            items.append({
                "id": row["id"],
                "cliente_id": row["cliente_id"],
                "variante_id": row["variante_id"],
                "created_at": row["created_at"],
                "sku": var_data.get("sku"),
                "nombre": nombre,
                "precio": var_data.get("precio"),
                "imagen_url": main_img
            })
        return items
    except Exception:
        # Fallback a consulta simple de deseos
        fallback = (
            supabase
            .table("deseos")
            .select("*")
            .eq("cliente_id", str(cliente_id))
            .order("created_at", desc=True)
            .execute()
        )
        return fallback.data or []

@router.delete(
    "/{cliente_id}/deseos/{variante_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
async def eliminar_deseo(
    cliente_id: uuid.UUID,
    variante_id: uuid.UUID
):
    """RF-21: Eliminar una variante de la lista de deseos."""
    supabase = get_supabase_client()
    if supabase is None:
        raise HTTPException(
            status_code=503,
            detail="Servicio de base de datos no disponible"
        )

    response = (
        supabase
        .table("deseos")
        .delete()
        .eq("cliente_id", str(cliente_id))
        .eq("variante_id", str(variante_id))
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=404,
            detail="El producto no se encuentra en la lista de deseos"
        )

    return None