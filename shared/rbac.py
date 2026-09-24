from dataclasses import dataclass
from typing import Any, FrozenSet, Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from backend.shared.security import decode_access_token


@dataclass(frozen=True)
class RBACRule:
    path_prefix: str
    allowed_roles: FrozenSet[str]
    methods: Optional[FrozenSet[str]] = None

    def matches(self, path: str, method: str) -> bool:
        return path.startswith(self.path_prefix) and (
            self.methods is None or method.upper() in self.methods
        )


def _current_user_from_payload(payload: dict[str, Any]) -> Optional[dict[str, Any]]:
    subject = payload.get("sub")
    if not subject:
        return None

    app_metadata = payload.get("app_metadata") or {}
    user_metadata = payload.get("user_metadata") or {}
    role = app_metadata.get("role") or user_metadata.get("role") or payload.get("role", "cliente")
    return {
        "user_id": subject,
        "email": payload.get("email"),
        "role": str(role).lower(),
        "payload": payload,
    }


class RBACAuthorizationMiddleware(BaseHTTPMiddleware):
    """Valida JWT y roles para rutas internas declaradas por reglas RBAC."""

    def __init__(self, app: Any, rules: list[RBACRule]):
        super().__init__(app)
        self.rules = rules

    async def dispatch(self, request: Request, call_next: Any):
        if request.method == "OPTIONS":
            return await call_next(request)

        matched_rule = next(
            (rule for rule in self.rules if rule.matches(request.url.path, request.method)),
            None,
        )
        if not matched_rule:
            return await call_next(request)

        authorization = request.headers.get("Authorization", "")
        if not authorization.lower().startswith("bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Se requiere autenticación mediante token Bearer"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        payload = decode_access_token(authorization.split(" ", 1)[1])
        current_user = _current_user_from_payload(payload) if payload else None
        if not current_user:
            return JSONResponse(
                status_code=401,
                content={"detail": "Token inválido, expirado o sin claim 'sub'"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        if current_user["role"] not in {role.lower() for role in matched_rule.allowed_roles}:
            return JSONResponse(
                status_code=403,
                content={"detail": "El rol del token no tiene permisos para esta operación"},
            )

        request.state.current_user = current_user
        return await call_next(request)