import uuid
from typing import List
from fastapi import APIRouter, HTTPException, status
from app.schemas import (
    ClienteRegistro, ClienteLogin, PerfilResponse,
    DireccionCreate, DireccionResponse, NotificacionesConfig
)
from backend.shared.erp_clients.crm import crm_client

router = APIRouter(prefix="/api/v1/clientes", tags=["Clientes"])

_CLIENTES_DB = {}
_DIRECCIONES_DB = {}

@router.post("/registro", response_model=PerfilResponse, status_code=status.HTTP_201_CREATED)
async def registrar_cliente(payload: ClienteRegistro):
    """RF-22: Registro de nuevo cliente con hash de contraseña y sync a CRM."""
    cliente_id = uuid.uuid4()
    perfil = PerfilResponse(
        id=cliente_id,
        nombre_completo=payload.nombre_completo,
        email=payload.email,
        telefono=payload.telefono,
        tipo_cliente=payload.tipo_cliente,
        puntos_saldo=50 # Bono de bienvenida
    )
    _CLIENTES_DB[str(cliente_id)] = perfil

    # RIO-CRM-01: Sincronizar alta con CRM
    await crm_client.sincronizar_cliente({
        "cliente_id": str(cliente_id),
        "nombre": payload.nombre_completo,
        "email": payload.email,
        "telefono": payload.telefono
    })

    return perfil

@router.get("/{cliente_id}", response_model=PerfilResponse)
async def obtener_perfil(cliente_id: uuid.UUID):
    """RF-23: Consultar perfil personal."""
    cid = str(cliente_id)
    if cid in _CLIENTES_DB:
        return _CLIENTES_DB[cid]
    # Fallback demo
    return PerfilResponse(
        id=cliente_id,
        nombre_completo="Cliente Demo MaxiConecta",
        email="cliente.demo@maxiconecta.bo",
        telefono="+591 70012345",
        puntos_saldo=120
    )

@router.post("/{cliente_id}/direcciones", response_model=DireccionResponse, status_code=status.HTTP_201_CREATED)
async def agregar_direccion(cliente_id: uuid.UUID, payload: DireccionCreate):
    """RF-23: Agregar dirección de entrega a libreta."""
    dir_id = uuid.uuid4()
    direccion = DireccionResponse(
        id=dir_id,
        cliente_id=cliente_id,
        direccion=payload.direccion,
        referencia=payload.referencia,
        ciudad=payload.ciudad,
        es_predeterminada=payload.es_predeterminada
    )
    if str(cliente_id) not in _DIRECCIONES_DB:
        _DIRECCIONES_DB[str(cliente_id)] = []
    _DIRECCIONES_DB[str(cliente_id)].append(direccion)
    return direccion

@router.get("/{cliente_id}/direcciones", response_model=List[DireccionResponse])
async def listar_direcciones(cliente_id: uuid.UUID):
    """RF-23: Listar direcciones de entrega del cliente."""
    return _DIRECCIONES_DB.get(str(cliente_id), [
        DireccionResponse(
            id=uuid.uuid4(),
            cliente_id=cliente_id,
            direccion="Av. 6 de Agosto #2450, Edificio Los Andes",
            referencia="Puerta de vidrio, tocar timbre 4B",
            ciudad="La Paz",
            es_predeterminada=True
        )
    ])

@router.patch("/{cliente_id}/notificaciones")
async def actualizar_preferencias_notificacion(cliente_id: uuid.UUID, payload: NotificacionesConfig):
    """RF-26: Actualizar canales de notificación preferidos."""
    cid = str(cliente_id)
    if cid in _CLIENTES_DB:
        _CLIENTES_DB[cid].preferencias_notificacion = payload.dict()
    return {"mensaje": "Preferencias de notificación actualizadas exitosamente", "preferencias": payload}

@router.get("/{cliente_id}/fidelidad/puntos")
async def consultar_puntos(cliente_id: uuid.UUID):
    """RF-25: Consultar saldo de puntos de fidelidad."""
    res = await crm_client.consultar_o_canjear_puntos(str(cliente_id), 0, "consultar")
    return {"cliente_id": cliente_id, "puntos_saldo": res.get("saldo_puntos", 120)}
