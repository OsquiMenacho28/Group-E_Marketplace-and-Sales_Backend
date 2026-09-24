from typing import Optional, Dict
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field

class ClienteRegistro(BaseModel):
    nombre_completo: str = Field(..., min_length=2, description="Nombre completo del cliente")
    email: EmailStr = Field(..., description="Correo electrónico válido")
    password: str = Field(..., min_length=6, description="Contraseña de al menos 6 caracteres")
    telefono: Optional[str] = None
    nit_ci: Optional[str] = None
    razon_social: Optional[str] = None
    tipo_cliente: str = "retail"

class ClienteLogin(BaseModel):
    email: EmailStr = Field(..., description="Correo electrónico registrado")
    password: str = Field(..., description="Contraseña")

class PerfilResponse(BaseModel):
    id: UUID
    user_id: Optional[UUID] = None
    nombre_completo: str
    email: str
    telefono: Optional[str] = None
    nit_ci: Optional[str] = None
    razon_social: Optional[str] = None
    tipo_cliente: str = "retail"
    role: str = "cliente"
    sucursal_id: Optional[str] = None
    puntos_saldo: int = 0
    preferencias_notificacion: Dict[str, bool] = {"email": True, "sms": False, "whatsapp": False}
    mensaje: Optional[str] = None

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 3600
    user: PerfilResponse

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class DireccionCreate(BaseModel):
    direccion: str
    referencia: Optional[str] = None
    ciudad: str
    es_predeterminada: bool = False

class DireccionResponse(DireccionCreate):
    id: UUID
    cliente_id: UUID

class NotificacionesConfig(BaseModel):
    email: bool = True
    sms: bool = False
    whatsapp: bool = False
