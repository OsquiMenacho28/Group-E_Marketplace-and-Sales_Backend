from typing import Optional, Dict
from uuid import UUID
from pydantic import BaseModel

class ClienteRegistro(BaseModel):
    nombre_completo: str
    email: str
    password: str
    telefono: Optional[str] = None
    nit_ci: Optional[str] = None
    razon_social: Optional[str] = None
    tipo_cliente: str = "retail"

class ClienteLogin(BaseModel):
    email: str
    password: str

class PerfilResponse(BaseModel):
    id: UUID
    nombre_completo: str
    email: str
    telefono: Optional[str] = None
    tipo_cliente: str = "retail"
    puntos_saldo: int = 0
    preferencias_notificacion: Dict[str, bool] = {"email": True, "sms": False, "whatsapp": False}

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
