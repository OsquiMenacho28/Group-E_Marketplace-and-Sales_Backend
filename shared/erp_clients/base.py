import logging
from typing import Optional, Dict, Any
import httpx
from backend.shared.config import settings

logger = logging.getLogger("maxiconecta.erp")

class BaseERPClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.timeout = settings.ERP_TIMEOUT_SECONDS

    async def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as exc:
            logger.warning(f"Falla de comunicación con ERP [{url}]: {exc}. Retornando respuesta fallback.")
            return {"status": "fallback", "error": str(exc)}

    async def post(self, path: str, json_data: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=json_data)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as exc:
            logger.warning(f"Falla de comunicación con ERP [{url}]: {exc}. Retornando respuesta fallback.")
            return {"status": "fallback", "error": str(exc)}
