import uuid
from typing import Dict, Any
from backend.shared.config import settings
from backend.shared.erp_clients.base import BaseERPClient

class PagosClient(BaseERPClient):
    def __init__(self):
        super().__init__(settings.ERP_PAGOS_URL)

    async def procesar_cobro(self, monto: float, metodo: str, moneda: str = "BOB") -> Dict[str, Any]:
        """RIO-PAG-01: Solicitar procesamiento de cobro."""
        payload = {"monto": monto, "metodo": metodo, "moneda": moneda}
        res = await self.post("/api/v1/cobros/procesar", payload)
        if res.get("status") == "fallback":
            return {
                "transaccion_id": f"tx-{uuid.uuid4().hex[:10]}",
                "estado": "aprobado",
                "modo": "mock_fallback"
            }
        return res

    async def emitir_factura(self, datos_fiscales: Dict[str, Any]) -> Dict[str, Any]:
        """RIO-PAG-02: Transmitir detalle fiscal para emisión y timbrado legal (CUF)."""
        res = await self.post("/api/v1/facturas/emitir", datos_fiscales)
        if res.get("status") == "fallback":
            return {
                "numero_factura": 10052,
                "cuf": f"CUF-{uuid.uuid4().hex[:16].upper()}",
                "estado": "timbrada",
                "modo": "mock_fallback"
            }
        return res

    async def reversar_cobro(self, transaccion_id: str, monto: float) -> Dict[str, Any]:
        """RIO-PAG-03: Reversión del cobro y nota de crédito."""
        payload = {"transaccion_id": transaccion_id, "monto": monto}
        res = await self.post("/api/v1/facturas/reversion", payload)
        if res.get("status") == "fallback":
            return {
                "nota_credito": f"NC-{uuid.uuid4().hex[:8].upper()}",
                "reembolso_estado": "procesado",
                "modo": "mock_fallback"
            }
        return res

pagos_client = PagosClient()
