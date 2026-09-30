import uuid
import hashlib
from typing import Dict, Any, List
from backend.shared.config import settings
from backend.shared.erp_clients.base import BaseERPClient
from backend.shared import stock_ledger

# Red de sucursales simulada para la respuesta de fallback de disponibilidad
# multi-sucursal (RIO-INV-01), en tanto el ERP real de Inventarios no esté
# desplegado/alcanzable. Se usa únicamente cuando la llamada HTTP real falla.
_SUCURSALES_SIMULADAS = [
    {"sucursal_id": "SUC-LP-CENTRAL", "sucursal_nombre": "Sucursal Central - La Paz"},
    {"sucursal_id": "SUC-LP-SOPOCACHI", "sucursal_nombre": "Sucursal Sopocachi - La Paz"},
    {"sucursal_id": "SUC-SCZ-EQUIPETROL", "sucursal_nombre": "Sucursal Equipetrol - Santa Cruz"},
    {"sucursal_id": "SUC-CBB-CENTRO", "sucursal_nombre": "Sucursal Centro - Cochabamba"},
]


class InventariosClient(BaseERPClient):
    def __init__(self):
        super().__init__(settings.ERP_INVENTARIOS_URL)

    async def consultar_disponibilidad(self, sku: str, sucursal_id: str = None) -> Dict[str, Any]:
        """RIO-INV-01: Consultar stock en tiempo real."""
        params = {"sku": sku}
        if sucursal_id:
            params["sucursal_id"] = sucursal_id
        res = await self.get(f"/api/v1/stock/{sku}", params=params)
        if res.get("status") == "fallback":
            stock_simulado = await stock_ledger.available_stock(sku)
            return {"sku": sku, "stock_disponible": stock_simulado, "modo": "mock_fallback"}
        return res

    async def consultar_disponibilidad_multisucursal(self, sku_o_nombre: str) -> Dict[str, Any]:
        """
        Extensión de RIO-INV-01 usada por la consulta rápida de stock (F3):
        retorna el desglose de disponibilidad por sucursal para un SKU dado.
        SIMULA LA INTEGRACIÓN por el momento (el ERP de Inventarios aún no
        expone este endpoint), degradándose siempre a datos de fallback
        deterministas para que la demo sea reproducible.
        """
        params = {"q": sku_o_nombre}
        res = await self.get("/api/v1/stock/multisucursal", params=params)
        if res.get("status") == "fallback":
            sucursales = []
            for suc in _SUCURSALES_SIMULADAS:
                seed = int(hashlib.md5(f"{sku_o_nombre}:{suc['sucursal_id']}".encode()).hexdigest(), 16)
                sucursales.append({
                    **suc,
                    "stock_disponible": seed % 15,  # 0 a 14 unidades por sucursal
                })
            return {"query": sku_o_nombre, "sucursales": sucursales, "modo": "mock_fallback"}
        return res

    async def reservar_stock(self, items: List[Dict[str, Any]], ttl_segundos: int = 900) -> Dict[str, Any]:
        """RIO-INV-02: Solicitar reserva temporal de stock al iniciar checkout."""
        payload = {"items": items, "ttl_segundos": ttl_segundos}
        res = await self.post("/api/v1/reservas-stock", payload)
        if res.get("status") == "fallback":
            mock_id = f"RES-MOCK-{uuid.uuid4().hex[:6].upper()}"
            ok, mensaje = await stock_ledger.reserve(mock_id, stock_ledger.group_by_sku(items), ttl_segundos)
            if not ok:
                return {"status": "RECHAZADA", "mensaje": mensaje, "modo": "mock_fallback"}
            return {"reserva_id": mock_id, "status": "CONFIRMADA", "modo": "mock_fallback"}
        return res

    async def descuento_definitivo(self, reserva_id: str, orden_id: str) -> Dict[str, Any]:
        """RIO-INV-03: Descuento definitivo de inventario tras confirmarse el pago."""
        payload = {"reserva_id": reserva_id, "orden_id": orden_id}
        res = await self.post("/api/v1/stock/descuento-definitivo", payload)
        if res.get("status") == "fallback":
            await stock_ledger.commit(reserva_id)
            return {"status": "DESCONTADO", "modo": "mock_fallback"}
        return res

    async def descuento_directo(self, items: List[Dict[str, Any]], orden_id: str) -> Dict[str, Any]:
        """RIO-INV-03: Descuento inmediato de una venta presencial (POS) sin reserva previa."""
        payload = {"items": items, "orden_id": orden_id}
        res = await self.post("/api/v1/stock/descuento-directo", payload)
        if res.get("status") == "fallback":
            ok, mensaje = await stock_ledger.consume(stock_ledger.group_by_sku(items))
            if not ok:
                return {"status": "RECHAZADA", "mensaje": mensaje, "modo": "mock_fallback"}
            return {"status": "DESCONTADO", "modo": "mock_fallback"}
        return res

    async def liberar_reserva(self, reserva_id: str, items: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """RIO-INV-02: Liberar reserva temporal de existencias si expira el TTL o se cancela el checkout."""
        payload = {"reserva_id": reserva_id, "items": items or []}
        res = await self.post("/api/v1/reservas-stock/liberar", payload)
        if res.get("status") == "fallback":
            await stock_ledger.release(reserva_id)
            return {"reserva_id": reserva_id, "status": "LIBERADA", "modo": "mock_fallback"}
        return res

    async def reingreso_por_devolucion(self, orden_id: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """RIO-INV-04: Reingreso de productos por cancelación o devolución."""
        payload = {"orden_id": orden_id, "items": items}
        res = await self.post("/api/v1/stock/reingreso", payload)
        if res.get("status") == "fallback":
            await stock_ledger.restock(stock_ledger.group_by_sku(items))
            return {"status": "REINGRESADO", "modo": "mock_fallback"}
        return res

inventarios_client = InventariosClient()
