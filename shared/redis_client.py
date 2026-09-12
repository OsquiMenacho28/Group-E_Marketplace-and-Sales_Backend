import json
import logging
from typing import Optional, Dict, Any
import redis.asyncio as aioredis
from backend.shared.config import settings

logger = logging.getLogger("maxiconecta.redis")

_redis_instance: Optional[aioredis.Redis] = None

async def get_redis() -> aioredis.Redis:
    """
    Retorna la instancia global del cliente asíncrono Redis.
    """
    global _redis_instance
    if _redis_instance is None:
        _redis_instance = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
    return _redis_instance

# ------------------------------------------------------------------------------
# Helpers para Carrito Persistente (RF-13)
# ------------------------------------------------------------------------------
async def get_cart_from_cache(client_or_session_id: str) -> Dict[str, Any]:
    redis = await get_redis()
    key = f"cart:{client_or_session_id}"
    raw = await redis.get(key)
    if raw:
        try:
            return json.loads(raw)
        except Exception:
            return {"items": [], "subtotal": 0.0}
    return {"items": [], "subtotal": 0.0}

async def save_cart_to_cache(client_or_session_id: str, cart_data: Dict[str, Any], ttl_seconds: int = 86400 * 7):
    redis = await get_redis()
    key = f"cart:{client_or_session_id}"
    await redis.setex(key, ttl_seconds, json.dumps(cart_data))

async def delete_cart_from_cache(client_or_session_id: str):
    redis = await get_redis()
    await redis.delete(f"cart:{client_or_session_id}")

# ------------------------------------------------------------------------------
# Helpers para Reserva Temporal de Stock con TTL (RF-14, RIO-INV-02)
# ------------------------------------------------------------------------------
async def lock_stock_reservation(variante_id: str, reserva_id: str, cantidad: int, ttl_seconds: int = 900) -> bool:
    """
    Bloquea temporalmente el stock en Redis durante el checkout digital (TTL default: 15 min).
    """
    redis = await get_redis()
    key = f"lock:stock:{variante_id}:{reserva_id}"
    payload = json.dumps({"reserva_id": reserva_id, "cantidad": cantidad})
    # SET con condición NX (solo si no existe) y expiración EX
    success = await redis.set(key, payload, ex=ttl_seconds, nx=True)
    return bool(success)

async def release_stock_reservation(variante_id: str, reserva_id: str) -> bool:
    """
    Libera la reserva temporal si el checkout falla o se cancela.
    """
    redis = await get_redis()
    key = f"lock:stock:{variante_id}:{reserva_id}"
    deleted = await redis.delete(key)
    return bool(deleted > 0)
