from functools import wraps
from inspect import isawaitable
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set, TypeVar
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from backend.shared.config import settings

security_scheme = HTTPBearer(auto_error=False)

Endpoint = TypeVar("Endpoint", bound=Callable[..., Any])

def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decodifica y valida la firma del token JWT emitido por Supabase Auth.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_aud": False}
        )
        return payload
    except JWTError:
        return None

async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)
) -> Dict[str, Any]:
    """
    Inyección de dependencias para obtener el usuario autenticado del token Bearer.
    """
    middleware_user = getattr(request.state, "current_user", None)
    if middleware_user:
        return middleware_user

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere autenticación mediante token Bearer",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    subject = payload.get("sub")
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token no contiene el claim requerido 'sub'",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # En Supabase Auth, el rol se almacena en app_metadata o user_metadata
    user_metadata = payload.get("user_metadata", {})
    app_metadata = payload.get("app_metadata", {})
    role = app_metadata.get("role") or user_metadata.get("role") or payload.get("role", "cliente")

    return {
        "user_id": subject,
        "email": payload.get("email"),
        "role": role,
        "payload": payload
    }

def require_role(allowed_roles: List[str]):
    """
    Controlador de acceso RBAC para endpoints protegidos.
    """
    async def role_checker(current_user: Dict[str, Any] = Depends(get_current_user)):
        user_role = current_user.get("role", "").lower()
        if user_role not in [r.lower() for r in allowed_roles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permisos insuficientes. Requiere uno de los roles: {allowed_roles}"
            )
        return current_user
    return role_checker


def require_jwt_claims(
    *required_claims: str,
    allowed_roles: Optional[Set[str]] = None,
) -> Callable[[Endpoint], Endpoint]:
    """Protege endpoints internos tras la dependencia ``get_current_user``.

    El endpoint debe declarar ``current_user=Depends(get_current_user)``. FastAPI
    valida el Bearer token antes de que el decorador compruebe los claims y roles.
    """
    normalized_roles = {role.lower() for role in allowed_roles or set()}

    def decorator(endpoint: Endpoint) -> Endpoint:
        @wraps(endpoint)
        async def wrapped(*args: Any, **kwargs: Any) -> Any:
            current_user = kwargs.get("current_user")
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="No se pudo obtener el contexto JWT del usuario",
                )

            payload = current_user.get("payload", {})
            missing_claims = [claim for claim in required_claims if not payload.get(claim)]
            if missing_claims:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Faltan claims JWT requeridos: {', '.join(missing_claims)}",
                )

            user_role = str(current_user.get("role", "")).lower()
            if normalized_roles and user_role not in normalized_roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="El rol del token no tiene permisos para esta operación",
                )

            result = endpoint(*args, **kwargs)
            return await result if isawaitable(result) else result

        return wrapped  # type: ignore[return-value]

    return decorator
