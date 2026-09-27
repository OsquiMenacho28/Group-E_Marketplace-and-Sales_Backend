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

async def save_suspended_sale(sale_id: str, sale_data: Dict[str, Any]):
    """
    Guarda temporalmente una venta suspendida en Redis (con fallback en memoria).
    """
    global _redis_unavailable
    key = f"pos:venta_suspendida:{sale_id}"
    payload = json.dumps(sale_data)
    redis = await get_redis()
    if redis:
        try:
            await redis.set(key, payload)
            return
        except Exception:
            _redis_unavailable = True

    _in_memory_store[key] = {"value": payload}


async def get_suspended_sale(sale_id: str) -> Optional[Dict[str, Any]]:
    """
    Obtiene una venta suspendida por su ID.
    """
    global _redis_unavailable
    key = f"pos:venta_suspendida:{sale_id}"
    raw = None
    redis = await get_redis()
    if redis:
        try:
            raw = await redis.get(key)
        except Exception:
            _redis_unavailable = True

    if not raw:
        entry = _in_memory_store.get(key)
        if entry:
            raw = entry.get("value")

    if not raw:
        return None

    try:
        return json.loads(raw)
    except Exception:
        return None


async def list_suspended_sales() -> List[Dict[str, Any]]:
    """
    Lista todas las ventas actualmente suspendidas.
    """
    global _redis_unavailable
    sales = []
    redis = await get_redis()
    if redis:
        try:
            async for key in redis.scan_iter(match="pos:venta_suspendida:*"):
                raw = await redis.get(key)
                if raw:
                    try:
                        sales.append(json.loads(raw))
                    except Exception:
                        continue
            return sales
        except Exception:
            _redis_unavailable = True

    for k, entry in _in_memory_store.items():
        if k.startswith("pos:venta_suspendida:"):
            try:
                sales.append(json.loads(entry["value"]))
            except Exception:
                continue

    return sales


async def delete_suspended_sale(sale_id: str) -> bool:
    """
    Elimina una venta suspendida de Redis o de memoria al recuperarla.
    """
    global _redis_unavailable
    key = f"pos:venta_suspendida:{sale_id}"
    deleted_redis = False
    if not _redis_unavailable:
        try:
            redis = await get_redis()
            if redis:
                deleted = await redis.delete(key)
                deleted_redis = deleted > 0
        except Exception:
            _redis_unavailable = True

    deleted_mem = _in_memory_store.pop(key, None) is not None
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
