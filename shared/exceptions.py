from typing import Any, Optional
from fastapi import Request, status
from fastapi.responses import JSONResponse

class MaxiConectaException(Exception):
    """Clase base para excepciones de dominio en MaxiConecta."""
    def __init__(self, message: str, status_code: int = 400, details: Optional[Any] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}

class EntityNotFoundException(MaxiConectaException):
    def __init__(self, entity: str, entity_id: Any):
        super().__init__(
            message=f"{entity} con identificador '{entity_id}' no fue encontrado.",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"entity": entity, "id": str(entity_id)}
        )

class InsufficientStockException(MaxiConectaException):
    def __init__(self, sku: str, requested: int, available: int):
        super().__init__(
            message=f"Stock insuficiente para el SKU '{sku}'. Solicitado: {requested}, Disponible: {available}.",
            status_code=status.HTTP_409_CONFLICT,
            details={"sku": sku, "requested": requested, "available": available}
        )

class InvalidOrderTransitionException(MaxiConectaException):
    def __init__(self, current_state: str, next_state: str):
        super().__init__(
            message=f"Transición de estado de orden inválida de '{current_state}' a '{next_state}'.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"from": current_state, "to": next_state}
        )

class ClosedBoxException(MaxiConectaException):
    def __init__(self, sucursal_id: str):
        super().__init__(
            message=f"No es posible procesar operaciones de venta sin una caja abierta en la sucursal '{sucursal_id}'.",
            status_code=status.HTTP_403_FORBIDDEN,
            details={"sucursal_id": sucursal_id}
        )

async def maxiconecta_exception_handler(request: Request, exc: MaxiConectaException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.__class__.__name__,
            "message": exc.message,
            "details": exc.details,
            "path": request.url.path
        }
    )
