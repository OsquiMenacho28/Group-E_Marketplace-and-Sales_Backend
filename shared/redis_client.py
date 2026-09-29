import json
import logging
import time
from typing import Optional, Dict, Any, List
import redis.asyncio as aioredis
from backend.shared.config import settings

logger = logging.getLogger("maxiconecta.redis")

_redis_instance: Optional[aioredis.Redis] = None
_redis_unavailable: bool = False
_in_memory_store: Dict[str, Dict[str, Any]] = {}  # Fallback en memoria si Redis no está disponible

async def get_redis() -> Optional[aioredis.Redis]:
    """
    Retorna la instancia global del cliente asíncrono Redis.
    Si Redis no está disponible o falla la conexión, retorna None para usar el almacén en memoria.
    """
    global _redis_instance, _redis_unavailable
    if _redis_unavailable:
        return None

    if _redis_instance is None:
        try:
            _redis_instance = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=1.0,
                socket_connect_timeout=1.0
            )
        except Exception as exc:
            logger.debug("No se pudo instanciar Redis (%s), activando modo en memoria", exc)
            _redis_unavailable = True
            return None
    return _redis_instance

# ------------------------------------------------------------------------------
# Helpers para Carrito Persistente (RF-13)
# ------------------------------------------------------------------------------
async def get_cart_from_cache(client_or_session_id: str) -> Dict[str, Any]:
    global _redis_unavailable
    key = f"cart:{client_or_session_id}"
    redis = await get_redis()
    if redis:
        try:
            raw = await redis.get(key)
            if raw:
                return json.loads(raw)
            return {"items": [], "subtotal": 0.0}
        except Exception as exc:
            logger.debug("Falla leyendo carrito de Redis: %s", exc)
            _redis_unavailable = True

    entry = _in_memory_store.get(key)
    if entry and entry["expires_at"] > time.time():
        return json.loads(entry["value"])
    return {"items": [], "subtotal": 0.0}

async def save_cart_to_cache(client_or_session_id: str, cart_data: Dict[str, Any], ttl_seconds: int = 86400 * 7):
    global _redis_unavailable
    key = f"cart:{client_or_session_id}"
    payload = json.dumps(cart_data)
    redis = await get_redis()
    if redis:
        try:
            await redis.setex(key, ttl_seconds, payload)
            return
        except Exception as exc:
            logger.debug("Falla guardando carrito en Redis: %s", exc)
            _redis_unavailable = True

    _in_memory_store[key] = {
        "value": payload,
        "expires_at": time.time() + ttl_seconds
    }

async def delete_cart_from_cache(client_or_session_id: str):
    global _redis_unavailable
    key = f"cart:{client_or_session_id}"
    redis = await get_redis()
    if redis:
        try:
            await redis.delete(key)
        except Exception:
            _redis_unavailable = True
    _in_memory_store.pop(key, None)

# ------------------------------------------------------------------------------
# Helpers para Reserva Temporal de Stock con TTL (RF-14, RIO-INV-02)
# ------------------------------------------------------------------------------
async def lock_stock_reservation(variante_id: str, reserva_id: str, cantidad: int, ttl_seconds: int = 900) -> bool:
    """
    Bloquea temporalmente el stock en Redis durante el checkout digital (TTL default: 15 min).
    """
    global _redis_unavailable
    key = f"lock:stock:{variante_id}:{reserva_id}"
    payload = json.dumps({"reserva_id": reserva_id, "cantidad": cantidad})
    redis = await get_redis()
    if redis:
        try:
            success = await redis.set(key, payload, ex=ttl_seconds, nx=True)
            return bool(success)
        except Exception as exc:
            logger.debug("Falla locking stock en Redis: %s", exc)
            _redis_unavailable = True

    if key in _in_memory_store and _in_memory_store[key]["expires_at"] > time.time():
        return False
    _in_memory_store[key] = {
        "value": payload,
        "expires_at": time.time() + ttl_seconds
    }
    return True

async def release_stock_reservation(variante_id: str, reserva_id: str) -> bool:
    """
    Libera la reserva temporal si el checkout falla o se cancela.
    """
    global _redis_unavailable
    key = f"lock:stock:{variante_id}:{reserva_id}"
    redis = await get_redis()
    if redis:
        try:
            deleted = await redis.delete(key)
            return bool(deleted > 0)
        except Exception:
            _redis_unavailable = True

    deleted = 1 if key in _in_memory_store else 0
    _in_memory_store.pop(key, None)
    return bool(deleted > 0)
async def crear_reserva_stock(
    reserva_id: str,
    cliente_id: str,
    items: List[Dict[str, Any]],
    ttl_seconds: int = 900
) -> Dict[str, Any]:
    """
    RF-14: Crea una reserva estructurada en Redis con clave reserva:{reserva_id}.
    Bloquea cada variante individualmente y registra el tiempo de expiración.
    """
    global _redis_unavailable
    key = f"reserva:{reserva_id}"
    now = time.time()
    reservation_data = {
        "reserva_id": reserva_id,
        "cliente_id": cliente_id,
        "items": items,
        "ttl_seconds": ttl_seconds,
        "created_at": now,
        "expires_at": now + ttl_seconds,
        "status": "ACTIVA"
    }
    payload = json.dumps(reservation_data)

    redis = await get_redis()
    if redis:
        try:
            await redis.setex(key, ttl_seconds, payload)
            for item in items:
                var_id = str(item.get("variante_id", ""))
                cant = int(item.get("cantidad", 1))
                await lock_stock_reservation(var_id, reserva_id, cant, ttl_seconds)
            return reservation_data
        except Exception as exc:
            logger.debug("Falla creando reserva en Redis: %s", exc)
            _redis_unavailable = True

    _in_memory_store[key] = {
        "value": payload,
        "expires_at": now + ttl_seconds
    }
    for item in items:
        var_id = str(item.get("variante_id", ""))
        cant = int(item.get("cantidad", 1))
        await lock_stock_reservation(var_id, reserva_id, cant, ttl_seconds)

    return reservation_data

async def consultar_reserva(reserva_id: str) -> Optional[Dict[str, Any]]:
    """
    RF-14: Consulta el estado y los segundos restantes de una reserva activa.
    Retorna None si la clave ya expiró en Redis.
    """
    global _redis_unavailable
    key = f"reserva:{reserva_id}"
    raw = None
    ttl_restante = 0

    redis = await get_redis()
    if redis:
        try:
            raw = await redis.get(key)
            if raw:
                ttl_restante = await redis.ttl(key)
        except Exception:
            _redis_unavailable = True

    if not raw:
        entry = _in_memory_store.get(key)
        if entry:
            restante = int(entry["expires_at"] - time.time())
            if restante > 0:
                raw = entry["value"]
                ttl_restante = restante
            else:
                _in_memory_store.pop(key, None)

    if not raw:
        return None

    data = json.loads(raw)
    data["segundos_restantes"] = max(0, ttl_restante)
    if data["segundos_restantes"] == 0:
        data["status"] = "EXPIRADA"
    return data

async def confirmar_reserva_stock(reserva_id: str) -> bool:
    """
    RF-14 / RIO-INV-03: Marca la reserva como confirmada al completarse la orden.
    """
    global _redis_unavailable
    reserva = await consultar_reserva(reserva_id)
    if not reserva:
        return False

    reserva["status"] = "CONFIRMADA"
    key = f"reserva:{reserva_id}"
    ttl = reserva.get("segundos_restantes", 60)
    payload = json.dumps(reserva)

    redis = await get_redis()
    if redis:
        try:
            await redis.setex(key, max(60, ttl), payload)
            return True
        except Exception:
            _redis_unavailable = True

    if key in _in_memory_store:
        _in_memory_store[key]["value"] = payload
    return True

async def liberar_reserva_stock(reserva_id: str) -> bool:
    """
    RF-14: Libera voluntariamente o por timeout una reserva y sus locks de variantes.
    """
    global _redis_unavailable
    reserva = await consultar_reserva(reserva_id)
    items = reserva.get("items", []) if reserva else []

    # Liberar locks individuales de variantes
    for item in items:
        var_id = str(item.get("variante_id", ""))
        await release_stock_reservation(var_id, reserva_id)

    key = f"reserva:{reserva_id}"
    redis = await get_redis()
    if redis:
        try:
            deleted = await redis.delete(key)
            return bool(deleted > 0)
        except Exception:
            _redis_unavailable = True

    deleted = 1 if key in _in_memory_store else 0
    _in_memory_store.pop(key, None)
    return bool(deleted > 0)

# ------------------------------------------------------------------------------
# Ventas suspendidas en POS (RF-12)
# ------------------------------------------------------------------------------

async def save_suspended_sale(
    caja_or_sale_id: str,
    sale_id_or_data: Any,
    sale_data: Optional[Dict[str, Any]] = None
):
    """
    Guarda temporalmente una venta suspendida en Redis (con fallback en memoria).
    Soporta firmas:
      - save_suspended_sale(caja_id, sale_id, sale_data)
      - save_suspended_sale(sale_id, sale_data)
    """
    global _redis_unavailable
    if sale_data is not None:
        caja_id = str(caja_or_sale_id)
        sale_id = str(sale_id_or_data)
        data = sale_data
    elif isinstance(sale_id_or_data, dict):
        caja_id = "general"
        sale_id = str(caja_or_sale_id)
        data = sale_id_or_data
    else:
        caja_id = str(caja_or_sale_id)
        sale_id = str(sale_id_or_data)
        data = {}

    key_caja = f"pos:venta_suspendida:{caja_id}:{sale_id}"
    key_direct = f"pos:venta_suspendida:{sale_id}"
    payload = json.dumps(data)

    _in_memory_store[key_caja] = {"value": payload}
    _in_memory_store[key_direct] = {"value": payload}

    redis = await get_redis()
    if redis:
        try:
            await redis.set(key_caja, payload)
            await redis.set(key_direct, payload)
        except Exception:
            _redis_unavailable = True


async def get_suspended_sale(
    caja_or_sale_id: str,
    sale_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Obtiene una venta suspendida perteneciente a una caja (o por ID directo).
    """
    global _redis_unavailable
    if sale_id is not None:
        caja_id = str(caja_or_sale_id)
        target_id = str(sale_id)
        keys = [
            f"pos:venta_suspendida:{caja_id}:{target_id}",
            f"pos:venta_suspendida:{target_id}",
        ]
    else:
        target_id = str(caja_or_sale_id)
        keys = [
            f"pos:venta_suspendida:{target_id}",
            f"pos:venta_suspendida:general:{target_id}",
        ]

    raw = None
    redis = await get_redis()
    if redis:
        try:
            for k in keys:
                raw = await redis.get(k)
                if raw:
                    break
        except Exception:
            _redis_unavailable = True

    if not raw:
        for k in keys:
            entry = _in_memory_store.get(k)
            if entry:
                raw = entry.get("value")
                break
        if not raw:
            for k, entry in _in_memory_store.items():
                if k.endswith(f":{target_id}"):
                    raw = entry.get("value")
                    break

    if not raw:
        return None

    try:
        return json.loads(raw)
    except Exception:
        return None


async def list_suspended_sales(
    caja_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Lista las ventas suspendidas de una caja específica (o todas si no se especifica).
    """
    global _redis_unavailable
    sales: List[Dict[str, Any]] = []
    seen_ids = set()
    pattern = f"pos:venta_suspendida:{caja_id}:*" if caja_id else "pos:venta_suspendida:*"

    redis = await get_redis()
    if redis:
        try:
            async for key in redis.scan_iter(match=pattern):
                raw = await redis.get(key)
                if raw:
                    try:
                        item = json.loads(raw)
                        iid = item.get("id") or key
                        if iid not in seen_ids:
                            seen_ids.add(iid)
                            sales.append(item)
                    except Exception:
                        continue
        except Exception:
            _redis_unavailable = True

    prefix = f"pos:venta_suspendida:{caja_id}:" if caja_id else "pos:venta_suspendida:"
    for k, entry in _in_memory_store.items():
        if k.startswith(prefix) or (not caja_id and k.startswith("pos:venta_suspendida:")):
            try:
                item = json.loads(entry["value"])
                iid = item.get("id") or k
                if iid not in seen_ids:
                    seen_ids.add(iid)
                    sales.append(item)
            except Exception:
                continue

    return sales


async def delete_suspended_sale(
    caja_or_sale_id: str,
    sale_id: Optional[str] = None
) -> bool:
    """
    Elimina una venta suspendida de Redis o de memoria al recuperarla.
    """
    global _redis_unavailable
    if sale_id is not None:
        caja_id = str(caja_or_sale_id)
        target_id = str(sale_id)
        keys = [
            f"pos:venta_suspendida:{caja_id}:{target_id}",
            f"pos:venta_suspendida:{target_id}",
        ]
    else:
        target_id = str(caja_or_sale_id)
        keys = [
            f"pos:venta_suspendida:{target_id}",
            f"pos:venta_suspendida:general:{target_id}",
        ]

    deleted_redis = False
    redis = await get_redis()
    if redis and not _redis_unavailable:
        try:
            for k in keys:
                res = await redis.delete(k)
                if res > 0:
                    deleted_redis = True
        except Exception:
            _redis_unavailable = True

    deleted_mem = False
    for k in list(_in_memory_store.keys()):
        if k in keys or k.endswith(f":{target_id}"):
            _in_memory_store.pop(k, None)
            deleted_mem = True

    return deleted_redis or deleted_mem

# ------------------------------------------------------------------------------
# Helpers de Caché de Disponibilidad de Stock (RF-07, RIO-INV-01)
# ------------------------------------------------------------------------------
# Cachea la respuesta del ERP de Inventarios con un TTL corto (30s por defecto)
# para mitigar la latencia de red hacia el ERP externo ante consultas repetidas
# del mismo SKU/sucursal (p. ej. varios clientes viendo el mismo producto).
#
# Se degrada de forma segura: si Redis no está disponible (p. ej. en un entorno
# de desarrollo sin el contenedor levantado), las funciones retornan None/False
# en lugar de propagar la excepción, y el endpoint que las use debe consultar
# directamente al ERP como si fuera un "cache miss".
STOCK_CACHE_TTL_SECONDS = 30

def _stock_cache_key(sku: str, sucursal_id: Optional[str] = None) -> str:
    return f"stock:{sku}:{sucursal_id or 'general'}"

async def get_stock_cache(sku: str, sucursal_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    global _redis_unavailable
    key = _stock_cache_key(sku, sucursal_id)
    if not _redis_unavailable:
        try:
            redis = await get_redis()
            if redis:
                raw = await redis.get(key)
                if raw:
                    return json.loads(raw)
        except Exception as exc:
            _redis_unavailable = True
            logger.warning(f"Redis no disponible para lectura de caché de stock ({sku}): {exc}. Se usará almacén en memoria.")

    if key in _in_memory_store:
        entry = _in_memory_store[key]
        if entry.get("expires_at", 0) > time.time():
            return json.loads(entry["value"])
        else:
            _in_memory_store.pop(key, None)
    return None

async def set_stock_cache(sku: str, data: Dict[str, Any], sucursal_id: Optional[str] = None, ttl_seconds: int = STOCK_CACHE_TTL_SECONDS) -> bool:
    global _redis_unavailable
    key = _stock_cache_key(sku, sucursal_id)
    payload = json.dumps(data, default=str)
    if not _redis_unavailable:
        try:
            redis = await get_redis()
            if redis:
                await redis.set(key, payload, ex=ttl_seconds)
                return True
        except Exception as exc:
            _redis_unavailable = True
            logger.warning(f"Redis no disponible para escritura de caché de stock ({sku}): {exc}. Se usará almacén en memoria.")

    _in_memory_store[key] = {
        "value": payload,
        "expires_at": time.time() + ttl_seconds
    }
    return True
