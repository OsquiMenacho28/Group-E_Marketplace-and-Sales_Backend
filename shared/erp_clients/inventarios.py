from typing import Dict, Any, List
from backend.shared.config import settings
from backend.shared.erp_clients.base import BaseERPClient

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
            return {"sku": sku, "stock_disponible": 100, "modo": "mock_fallback"}
        return res

    async def reservar_stock(self, items: List[Dict[str, Any]], ttl_segundos: int = 900) -> Dict[str, Any]:
        """RIO-INV-02: Solicitar reserva temporal de stock al iniciar checkout."""
        payload = {"items": items, "ttl_segundos": ttl_segundos}
        res = await self.post("/api/v1/reservas-stock", payload)
        if res.get("status") == "fallback":
            return {"reserva_id": "res-mock-12345", "status": "CONFIRMADA", "modo": "mock_fallback"}
        return res

    async def descuento_definitivo(self, reserva_id: str, orden_id: str) -> Dict[str, Any]:
        """RIO-INV-03: Descuento definitivo de inventario tras confirmarse el pago."""
        payload = {"reserva_id": reserva_id, "orden_id": orden_id}
        res = await self.post("/api/v1/stock/descuento-definitivo", payload)
        if res.get("status") == "fallback":
            return {"status": "DESCONTADO", "modo": "mock_fallback"}
        return res

    async def reingreso_por_devolucion(self, orden_id: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """RIO-INV-04: Reingreso de productos por cancelación o devolución."""
        payload = {"orden_id": orden_id, "items": items}
        res = await self.post("/api/v1/stock/reingreso", payload)
        if res.get("status") == "fallback":
            return {"status": "REINGRESADO", "modo": "mock_fallback"}
        return res

inventarios_client = InventariosClient()
