import uuid
from decimal import Decimal
from fastapi import APIRouter, HTTPException, status
from app.schemas import (
    ItemCarritoAdd, ItemCarritoResponse, CarritoResponse,
    AplicarCuponRequest, CheckoutInitRequest, CheckoutInitResponse
)
from backend.shared.redis_client import (
    get_cart_from_cache, save_cart_to_cache, delete_cart_from_cache,
    lock_stock_reservation
)
from backend.shared.erp_clients.inventarios import inventarios_client

router = APIRouter(prefix="/api/v1/carrito", tags=["Carrito y Checkout"])

_CUPONES_VALIDOS = {
    "MAXI10": Decimal("10.0"),  # 10%
    "BIENVENIDO": Decimal("20.0") # 20 BOB
}

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
    descuento = Decimal(str(raw.get("descuento", "0.0")))
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
    await save_cart_to_cache(identificador, raw)
    return await ver_carrito(identificador)

@router.delete("/{identificador}/items/{variante_id}", response_model=CarritoResponse)
async def remover_item_carrito(identificador: str, variante_id: str):
    """RF-13: Quitar ítem del carrito."""
    raw = await get_cart_from_cache(identificador)
    raw["items"] = [i for i in raw.get("items", []) if i["variante_id"] != variante_id]
    await save_cart_to_cache(identificador, raw)
    return await ver_carrito(identificador)

@router.post("/{identificador}/cupon", response_model=CarritoResponse)
async def aplicar_cupon(identificador: str, payload: AplicarCuponRequest):
    """RF-17: Validar y aplicar cupón de descuento."""
    codigo = payload.codigo.upper()
    if codigo not in _CUPONES_VALIDOS:
        raise HTTPException(status_code=400, detail="Cupón no válido o vencido")

    raw = await get_cart_from_cache(identificador)
    raw["cupon"] = codigo
    raw["descuento"] = float(_CUPONES_VALIDOS[codigo])
    await save_cart_to_cache(identificador, raw)
    return await ver_carrito(identificador)

@router.post("/{identificador}/checkout/iniciar", response_model=CheckoutInitResponse)
async def iniciar_checkout(identificador: str, payload: CheckoutInitRequest):
    """RF-14, RIO-INV-02: Bloqueo temporal de stock en Redis por 15 minutos (900s)."""
    raw = await get_cart_from_cache(identificador)
    items = raw.get("items", [])
    if not items:
        raise HTTPException(status_code=400, detail="El carrito está vacío")

    reserva_id = f"RES-{uuid.uuid4().hex[:8].upper()}"

    # Bloquear cada variante en Redis con TTL de 900s
    for item in items:
        await lock_stock_reservation(
            variante_id=item["variante_id"],
            reserva_id=reserva_id,
            cantidad=item["cantidad"],
            ttl_seconds=900
        )

    # Notificar al ERP de Inventarios (RIO-INV-02)
    await inventarios_client.reservar_stock(items, ttl_segundos=900)

    subtotal = sum(Decimal(str(i["cantidad"])) * Decimal(str(i["precio_unitario"])) for i in items)
    descuento = Decimal(str(raw.get("descuento", "0.0")))
    total = max(Decimal("0.0"), subtotal - descuento)

    return CheckoutInitResponse(
        reserva_id=reserva_id,
        ttl_expira_en_segundos=900,
        monto_total=total,
        metodo_pago=payload.metodo_pago
    )
