from typing import Dict, Any
from backend.shared.config import settings
from backend.shared.erp_clients.base import BaseERPClient

class ProduccionClient(BaseERPClient):
    def __init__(self):
        super().__init__(settings.ERP_PRODUCCION_URL)

    async def consultar_proyeccion(self, sku: str) -> Dict[str, Any]:
        """RIO-PRD-01: Consultar fechas estimadas de reabastecimiento / producción."""
        res = await self.get(f"/api/v1/produccion/proyeccion/{sku}")
        if res.get("status") == "fallback":
            return {
                "sku": sku,
                "lote_en_curso": "LOTE-2026-B",
                "cantidad_proyectada": 500,
                "fecha_estimada_ingreso": "2026-10-15",
                "modo": "mock_fallback"
            }
        return res

produccion_client = ProduccionClient()
