from typing import Dict, Any
from backend.shared.config import settings
from backend.shared.erp_clients.base import BaseERPClient

class ContabilidadClient(BaseERPClient):
    def __init__(self):
        super().__init__(settings.ERP_CONTABILIDAD_URL)

    async def registrar_asiento_venta(self, orden_data: Dict[str, Any]) -> Dict[str, Any]:
        """RIO-CON-01: Asiento contable de ventas."""
        res = await self.post("/api/v1/asientos/venta", orden_data)
        if res.get("status") == "fallback":
            return {"asiento_id": "ASI-VTA-001", "estado": "asentado", "modo": "mock_fallback"}
        return res

    async def registrar_costo_ventas(self, costo_data: Dict[str, Any]) -> Dict[str, Any]:
        """RIO-CON-02: Registro contable del costo de mercadería vendida."""
        res = await self.post("/api/v1/asientos/costo-ventas", costo_data)
        if res.get("status") == "fallback":
            return {"asiento_id": "ASI-CMV-001", "estado": "asentado", "modo": "mock_fallback"}
        return res

    async def registrar_reversion(self, reversion_data: Dict[str, Any]) -> Dict[str, Any]:
        """RIO-CON-04: Asientos de reversión por cancelaciones y devoluciones."""
        res = await self.post("/api/v1/asientos/reversion", reversion_data)
        if res.get("status") == "fallback":
            return {"asiento_id": "ASI-REV-001", "estado": "revertido", "modo": "mock_fallback"}
        return res

contabilidad_client = ContabilidadClient()
