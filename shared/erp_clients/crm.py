from typing import Dict, Any
from backend.shared.config import settings
from backend.shared.erp_clients.base import BaseERPClient

class CRMClient(BaseERPClient):
    def __init__(self):
        super().__init__(settings.ERP_CRM_URL)

    async def sincronizar_cliente(self, cliente_data: Dict[str, Any]) -> Dict[str, Any]:
        """RIO-CRM-01: Sincronizar datos de perfil y direcciones con el CRM."""
        res = await self.post("/api/v1/clientes/sync", cliente_data)
        if res.get("status") == "fallback":
            return {"crm_contact_id": "CRM-CNT-99", "estado": "sincronizado", "modo": "mock_fallback"}
        return res

    async def notificar_evento_compra(self, evento_data: Dict[str, Any]) -> Dict[str, Any]:
        """RIO-CRM-02: Notificar evento de compra para segmentación RFM."""
        res = await self.post("/api/v1/eventos/compra", evento_data)
        if res.get("status") == "fallback":
            return {"estado": "registrado", "modo": "mock_fallback"}
        return res

    async def consultar_o_canjear_puntos(self, cliente_id: str, puntos: int, accion: str) -> Dict[str, Any]:
        """RIO-CRM-03: Consulta, acumulación o redención de puntos de fidelidad."""
        payload = {"cliente_id": cliente_id, "puntos": puntos, "accion": accion}
        res = await self.post("/api/v1/fidelidad/transaccion", payload)
        if res.get("status") == "fallback":
            return {"saldo_puntos": 250, "estado": "exitoso", "modo": "mock_fallback"}
        return res

crm_client = CRMClient()
