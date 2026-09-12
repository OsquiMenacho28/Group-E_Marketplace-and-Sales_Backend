from typing import Optional, Dict, Any, List
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from backend.shared.config import settings

security_scheme = HTTPBearer(auto_error=False)

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
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)
) -> Dict[str, Any]:
    """
    Inyección de dependencias para obtener el usuario autenticado del token Bearer.
    """
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

    # En Supabase Auth, el rol se almacena en app_metadata o user_metadata
    user_metadata = payload.get("user_metadata", {})
    app_metadata = payload.get("app_metadata", {})
    role = app_metadata.get("role") or user_metadata.get("role") or payload.get("role", "cliente")

    return {
        "user_id": payload.get("sub"),
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
