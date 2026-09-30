"""
Libro de inventario simulado compartido (RIO-INV-01/02/03) mientras el ERP de
Inventarios no esté disponible. Vive en Redis para que Catálogo, Carrito,
Órdenes y POS consulten y descuenten exactamente el mismo stock.
"""
import asyncio
import hashlib
import json
import logging
import time
import uuid
from typing import Any, Dict, Iterable, Optional, Tuple

from backend.shared.redis_client import get_redis

logger = logging.getLogger("maxiconecta.stock_ledger")

_LOCK_KEY = "inv:lock"
_RESERVATION_GRACE_SECONDS = 3600

_memory: Dict[str, Any] = {}
_redis_ok: Optional[bool] = None


def simulated_base_stock(sku: str) -> int:
    seed = int(hashlib.md5(sku.encode()).hexdigest(), 16)
    return seed % 30


async def _redis():
    global _redis_ok
    if _redis_ok is False:
        return None
    client = await get_redis()
    if client is None:
        _redis_ok = False
        return None
    if _redis_ok is None:
        try:
            await client.ping()
            _redis_ok = True
        except Exception as exc:
            logger.warning("Redis no disponible para inventario simulado (%s); se usará memoria.", exc)
            _redis_ok = False
            return None
    return client


async def _exec(redis_operation, memory_operation):
    global _redis_ok
    client = await _redis()
    if client:
        try:
            return await redis_operation(client)
        except Exception as exc:
            logger.warning("Falla de Redis en inventario simulado (%s); se usará memoria.", exc)
            _redis_ok = False
    return memory_operation()


async def _get(key: str) -> Optional[str]:
    return await _exec(lambda c: c.get(key), lambda: _memory.get(key))


async def _set(key: str, value: str, ttl: Optional[int] = None) -> None:
    await _exec(lambda c: c.set(key, value, ex=ttl), lambda: _memory.__setitem__(key, value))


async def _delete(key: str) -> None:
    await _exec(lambda c: c.delete(key), lambda: _memory.pop(key, None))


async def _incrby(key: str, amount: int) -> int:
    def memory_incr() -> int:
        _memory[key] = str(int(_memory.get(key, 0)) + amount)
        return int(_memory[key])

    return int(await _exec(lambda c: c.incrby(key, amount), memory_incr))


async def _hgetall(key: str) -> Dict[str, str]:
    return await _exec(lambda c: c.hgetall(key), lambda: dict(_memory.get(key, {})))


async def _hset(key: str, field: str, value: str) -> None:
    await _exec(
        lambda c: c.hset(key, field, value),
        lambda: _memory.setdefault(key, {}).__setitem__(field, value),
    )


async def _hdel(key: str, *fields: str) -> None:
    if not fields:
        return

    def memory_hdel() -> None:
        for field in fields:
            _memory.get(key, {}).pop(field, None)

    await _exec(lambda c: c.hdel(key, *fields), memory_hdel)


async def _invalidate_stock_cache(sku: str) -> None:
    async def redis_invalidate(client) -> None:
        async for key in client.scan_iter(match=f"stock:{sku}:*"):
            await client.delete(key)

    await _exec(redis_invalidate, lambda: None)


class _LedgerLock:
    """Exclusión mutua entre servicios para verificar y reservar sin sobreventa."""

    def __init__(self) -> None:
        self.token = uuid.uuid4().hex

    async def __aenter__(self):
        for _ in range(100):
            acquired = await _exec(
                lambda c: c.set(_LOCK_KEY, self.token, nx=True, px=5000),
                lambda: True,
            )
            if acquired:
                return self
            await asyncio.sleep(0.05)
        raise RuntimeError("No se pudo bloquear el inventario para reservar stock")

    async def __aexit__(self, *exc_info):
        if await _get(_LOCK_KEY) == self.token:
            await _delete(_LOCK_KEY)


async def register_base_stock(sku: str, quantity: int) -> None:
    await _set(f"inv:base:{sku}", str(max(0, int(quantity))))


async def get_base_stock(sku: str) -> Optional[int]:
    raw = await _get(f"inv:base:{sku}")
    return int(raw) if raw is not None else None


async def _ensure_base_stock(sku: str) -> int:
    base = await get_base_stock(sku)
    if base is None:
        base = simulated_base_stock(sku)
        await register_base_stock(sku, base)
    return base


async def _reserved_quantity(sku: str, now: float) -> int:
    key = f"inv:reserved:{sku}"
    entries = await _hgetall(key)
    total = 0
    expired = []
    for reserva_id, raw in entries.items():
        entry = json.loads(raw)
        if entry["expires_at"] <= now:
            expired.append(reserva_id)
        else:
            total += int(entry["quantity"])
    await _hdel(key, *expired)
    return total


async def _available(sku: str, base: int, now: float) -> int:
    sold = int(await _get(f"inv:sold:{sku}") or 0)
    return max(0, base - sold - await _reserved_quantity(sku, now))


async def available_stock(sku: str, register_missing: bool = True) -> Optional[int]:
    base = await (_ensure_base_stock(sku) if register_missing else get_base_stock(sku))
    if base is None:
        return None
    return await _available(sku, base, time.time())


def group_by_sku(items: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    grouped: Dict[str, int] = {}
    for item in items:
        sku = str(item.get("sku") or item.get("variante_id") or "")
        if sku:
            grouped[sku] = grouped.get(sku, 0) + int(item.get("cantidad", 1))
    return grouped


async def reserve(reserva_id: str, requested: Dict[str, int], ttl_seconds: int) -> Tuple[bool, str]:
    now = time.time()
    async with _LedgerLock():
        for sku, quantity in requested.items():
            available = await _available(sku, await _ensure_base_stock(sku), now)
            if quantity > available:
                return False, f"Stock insuficiente para {sku}. Disponibles: {available}."
        entry_expiry = now + ttl_seconds
        for sku, quantity in requested.items():
            await _hset(
                f"inv:reserved:{sku}",
                reserva_id,
                json.dumps({"quantity": quantity, "expires_at": entry_expiry}),
            )
        await _set(f"inv:res:{reserva_id}", json.dumps(requested), ttl_seconds + _RESERVATION_GRACE_SECONDS)
    for sku in requested:
        await _invalidate_stock_cache(sku)
    return True, "Reserva confirmada"


async def _pop_reservation(reserva_id: str) -> Dict[str, int]:
    raw = await _get(f"inv:res:{reserva_id}")
    if not raw:
        return {}
    requested = json.loads(raw)
    for sku in requested:
        await _hdel(f"inv:reserved:{sku}", reserva_id)
    await _delete(f"inv:res:{reserva_id}")
    return requested


async def release(reserva_id: str) -> None:
    async with _LedgerLock():
        requested = await _pop_reservation(reserva_id)
    for sku in requested:
        await _invalidate_stock_cache(sku)


async def commit(reserva_id: str) -> None:
    async with _LedgerLock():
        requested = await _pop_reservation(reserva_id)
        for sku, quantity in requested.items():
            await _incrby(f"inv:sold:{sku}", quantity)
    for sku in requested:
        await _invalidate_stock_cache(sku)


async def consume(requested: Dict[str, int]) -> Tuple[bool, str]:
    """Descuento directo (venta POS): solo controla SKUs con stock registrado."""
    now = time.time()
    async with _LedgerLock():
        tracked: Dict[str, int] = {}
        for sku, quantity in requested.items():
            base = await get_base_stock(sku)
            if base is None:
                continue
            available = await _available(sku, base, now)
            if quantity > available:
                return False, f"Stock insuficiente para {sku}. Disponibles: {available}."
            tracked[sku] = quantity
        for sku, quantity in tracked.items():
            await _incrby(f"inv:sold:{sku}", quantity)
    for sku in tracked:
        await _invalidate_stock_cache(sku)
    return True, "Stock descontado"


async def restock(requested: Dict[str, int]) -> None:
    async with _LedgerLock():
        for sku, quantity in requested.items():
            remaining = await _incrby(f"inv:sold:{sku}", -quantity)
            if remaining < 0:
                await _set(f"inv:sold:{sku}", "0")
    for sku in requested:
        await _invalidate_stock_cache(sku)
