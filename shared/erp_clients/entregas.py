import uuid
from typing import Dict, Any
from backend.shared.config import settings
from backend.shared.erp_clients.base import BaseERPClient

class EntregasClient(BaseERPClient):
    def __init__(self):
        super().__init__(settings.ERP_ENTREGAS_URL)

    async def solicitar_despacho(self, despacho_data: Dict[str, Any]) -> Dict[str, Any]:
        """RIO-ENT-01: Generar orden de despacho y guía de paquetería."""
        res = await self.post("/api/v1/despachos/solicitar", despacho_data)
        if res.get("status") == "fallback":
            return {
                "guia_despacho": f"TRK-{uuid.uuid4().hex[:8].upper()}",
                "transportista": "MaxiLogística Express",
                "estado": "programado",
                "modo": "mock_fallback"
            }
        return res

    async def consultar_estado_envio(self, tracking_number: str) -> Dict[str, Any]:
        """RIO-ENT-02: Consumir estados de transporte en tiempo real."""
        res = await self.get(f"/api/v1/despachos/{tracking_number}/estado")
        if res.get("status") == "fallback":
            return {
                "tracking_number": tracking_number,
                "estado": "en_transito",
                "ubicacion_actual": "Centro de Distribución Central",
                "modo": "mock_fallback"
            }
        return res

entregas_client = EntregasClient()
