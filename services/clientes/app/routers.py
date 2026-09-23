import uuid
import logging
from typing import List, Dict, Any, Optional
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
try:
    from app.schemas import (
        ClienteRegistro, ClienteLogin, PerfilResponse, TokenResponse, RefreshTokenRequest,
        DireccionCreate, DireccionResponse, NotificacionesConfig
    )
except (ModuleNotFoundError, ImportError):
    from backend.services.clientes.app.schemas import (
        ClienteRegistro, ClienteLogin, PerfilResponse, TokenResponse, RefreshTokenRequest,
        DireccionCreate, DireccionResponse, NotificacionesConfig
    )
from backend.shared.security import (
    create_access_token, create_refresh_token, decode_access_token,
    get_password_hash, verify_password, get_current_user
)
from backend.shared.database import get_supabase_client, get_supabase_admin_client
from backend.shared.erp_clients.crm import crm_client

logger = logging.getLogger("maxiconecta.clientes")
router = APIRouter(prefix="/api/v1/clientes", tags=["Clientes y Autenticación"])

# ------------------------------------------------------------------------------
# ALMACÉN EN MEMORIA PARA DESARROLLO Y PRUEBAS (CON USUARIOS SEMILLA POR ROL)
# ------------------------------------------------------------------------------
_USERS_DB: Dict[str, Dict[str, Any]] = {}
_CLIENTES_DB: Dict[str, PerfilResponse] = {}
_DIRECCIONES_DB: Dict[str, List[DireccionResponse]] = {}

def _init_seed_users():
    """Inicializa cuentas semilla para pruebas ágiles de todos los roles."""
    seeds = [
        {
            "id": uuid.UUID("00000000-0000-0000-0000-000000000001"),
            "user_id": uuid.UUID("00000000-0000-0000-0000-000000000001"),
            "email": "admin@maxiconecta.bo",
            "password_hash": get_password_hash("Admin123!"),
            "nombre_completo": "Cesar Admin (Líder Grupo E)",
            "role": "administrador",
            "tipo_cliente": "corporativo_b2b",
            "puntos_saldo": 500,
            "sucursal_id": None
        },
        {
            "id": uuid.UUID("00000000-0000-0000-0000-000000000002"),
            "user_id": uuid.UUID("00000000-0000-0000-0000-000000000002"),
            "email": "cajero@maxiconecta.bo",
            "password_hash": get_password_hash("Cajero123!"),
            "nombre_completo": "Cajero Sucursal Central",
            "role": "cajero",
            "tipo_cliente": "retail",
            "puntos_saldo": 0,
            "sucursal_id": "sucursal-central-001"
        },
        {
            "id": uuid.UUID("00000000-0000-0000-0000-000000000003"),
            "user_id": uuid.UUID("00000000-0000-0000-0000-000000000003"),
            "email": "gerente@maxiconecta.bo",
            "password_hash": get_password_hash("Gerente123!"),
            "nombre_completo": "Gerente Comercial ERP",
            "role": "gerente_comercial",
            "tipo_cliente": "corporativo_b2b",
            "puntos_saldo": 0,
            "sucursal_id": None
        },
        {
            "id": uuid.UUID("00000000-0000-0000-0000-000000000004"),
            "user_id": uuid.UUID("00000000-0000-0000-0000-000000000004"),
            "email": "cliente@maxiconecta.bo",
            "password_hash": get_password_hash("Cliente123!"),
            "nombre_completo": "Carlos Perez (Cliente Retail)",
            "role": "cliente",
            "telefono": "+591 71234567",
            "tipo_cliente": "retail",
            "puntos_saldo": 120,
            "sucursal_id": None
        }
    ]
    for s in seeds:
        email = s["email"].lower()
        if email not in _USERS_DB:
            _USERS_DB[email] = s
            perfil = PerfilResponse(
                id=s["id"],
                user_id=s["user_id"],
                nombre_completo=s["nombre_completo"],
                email=s["email"],
                telefono=s.get("telefono"),
                tipo_cliente=s["tipo_cliente"],
                role=s["role"],
                sucursal_id=s["sucursal_id"],
                puntos_saldo=s["puntos_saldo"]
            )
            _CLIENTES_DB[str(s["id"])] = perfil

_init_seed_users()

# ------------------------------------------------------------------------------
# ENDPOINTS DE AUTENTICACIÓN (RF-22, US-22 / RF-49, US-49)
# ------------------------------------------------------------------------------

def _create_token_response(user_data: Dict[str, Any], perfil: PerfilResponse) -> TokenResponse:
    claims = {
        "sub": str(perfil.id),
        "user_id": str(perfil.id),
        "email": perfil.email,
        "role": perfil.role,
        "nombre_completo": perfil.nombre_completo,
        "sucursal_id": perfil.sucursal_id
    }
    access_token = create_access_token(claims, expires_delta=timedelta(hours=2))
    refresh_token = create_refresh_token(claims, expires_delta=timedelta(days=7))
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=7200,
        user=perfil
    )

@router.post("/auth/registro", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@router.post("/registro", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def registrar_cliente(payload: ClienteRegistro):
    """
    RF-22: Registro de nuevo cliente con hash de contraseña, bono de 50 puntos y sincronización a CRM.
    Emite tokens JWT de acceso y refresco.
    """
    email_clean = payload.email.lower().strip()
    if email_clean in _USERS_DB:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe una cuenta registrada con este correo electrónico."
        )

    cliente_id = uuid.uuid4()
    user_id = cliente_id

    # Intentar registro en Supabase Auth si está conectado
    supabase = get_supabase_client()
    if supabase:
        try:
            sb_res = supabase.auth.sign_up({
                "email": email_clean,
                "password": payload.password,
                "options": {
                    "data": {
                        "nombre_completo": payload.nombre_completo,
                        "role": "cliente"
                    }
                }
            })
            if sb_res and sb_res.user:
                user_id = uuid.UUID(sb_res.user.id)
        except Exception as e:
            logger.warning(f"No se pudo registrar en Supabase Auth directo (modo local fallback): {e}")

    # Guardar en estructura de datos
    user_record = {
        "id": cliente_id,
        "user_id": user_id,
        "email": email_clean,
        "password_hash": get_password_hash(payload.password),
        "nombre_completo": payload.nombre_completo,
        "telefono": payload.telefono,
        "nit_ci": payload.nit_ci,
        "razon_social": payload.razon_social,
        "role": "cliente",
        "tipo_cliente": payload.tipo_cliente,
        "puntos_saldo": 50, # Bono de bienvenida RF-22
        "sucursal_id": None
    }
    _USERS_DB[email_clean] = user_record

    perfil = PerfilResponse(
        id=cliente_id,
        user_id=user_id,
        nombre_completo=payload.nombre_completo,
        email=email_clean,
        telefono=payload.telefono,
        nit_ci=payload.nit_ci,
        razon_social=payload.razon_social,
        tipo_cliente=payload.tipo_cliente,
        role="cliente",
        puntos_saldo=50,
        mensaje="¡Bienvenido a MaxiConecta! Has recibido 50 puntos de bienvenida."
    )
    _CLIENTES_DB[str(cliente_id)] = perfil

    # RIO-CRM-01: Notificar alta a CRM corporativo
    try:
        await crm_client.sincronizar_cliente({
            "cliente_id": str(cliente_id),
            "nombre": payload.nombre_completo,
            "email": email_clean,
            "telefono": payload.telefono or "",
            "origen": "marketplace_web"
        })
    except Exception as e:
        logger.warning(f"Error sincronizando con CRM RIO: {e}")

    return _create_token_response(user_record, perfil)


@router.post("/auth/login", response_model=TokenResponse)
@router.post("/login", response_model=TokenResponse)
async def login_usuario(payload: ClienteLogin):
    """
    US-22 / US-49: Inicio de sesión multi-rol para Clientes, Cajeros (POS) y Administradores.
    Verifica credenciales, genera JWT con rol y claim de sucursal.
    """
    email_clean = payload.email.lower().strip()
    user_record = _USERS_DB.get(email_clean)

    # Si no está en memoria local, verificar en Supabase Auth si está configurado
    if not user_record:
        supabase = get_supabase_client()
        if supabase:
            try:
                auth_resp = supabase.auth.sign_in_with_password({
                    "email": email_clean,
                    "password": payload.password
                })
                if auth_resp and auth_resp.user:
                    u = auth_resp.user
                    uid = uuid.UUID(u.id)
                    u_meta = u.user_metadata or {}
                    app_meta = getattr(u, "app_metadata", {}) or {}
                    role = app_meta.get("role") or u_meta.get("role") or "cliente"
                    
                    user_record = {
                        "id": uid,
                        "user_id": uid,
                        "email": email_clean,
                        "password_hash": "",
                        "nombre_completo": u_meta.get("nombre_completo", email_clean.split("@")[0]),
                        "role": role,
                        "tipo_cliente": "retail",
                        "puntos_saldo": 50,
                        "sucursal_id": app_meta.get("sucursal_id")
                    }
                    _USERS_DB[email_clean] = user_record
            except Exception as e:
                logger.debug(f"Error Supabase Auth login: {e}")

    if not user_record or (user_record.get("password_hash") and not verify_password(payload.password, user_record["password_hash"])):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas. Verifique su correo o contraseña.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    cid = str(user_record["id"])
    if cid in _CLIENTES_DB:
        perfil = _CLIENTES_DB[cid]
    else:
        perfil = PerfilResponse(
            id=user_record["id"],
            user_id=user_record.get("user_id"),
            nombre_completo=user_record["nombre_completo"],
            email=user_record["email"],
            telefono=user_record.get("telefono"),
            nit_ci=user_record.get("nit_ci"),
            razon_social=user_record.get("razon_social"),
            tipo_cliente=user_record.get("tipo_cliente", "retail"),
            role=user_record["role"],
            sucursal_id=user_record.get("sucursal_id"),
            puntos_saldo=user_record.get("puntos_saldo", 0)
        )
        _CLIENTES_DB[cid] = perfil

    return _create_token_response(user_record, perfil)


@router.get("/auth/me", response_model=PerfilResponse)
@router.get("/me", response_model=PerfilResponse)
async def obtener_mi_perfil(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    US-22 / RF-22: Obtener perfil del usuario autenticado a partir de su Bearer Token JWT.
    """
    email = current_user.get("email", "").lower()
    user_id = current_user.get("user_id")

    # Buscar por id o por email
    if str(user_id) in _CLIENTES_DB:
        return _CLIENTES_DB[str(user_id)]

    if email in _USERS_DB:
        u = _USERS_DB[email]
        return _CLIENTES_DB.get(str(u["id"]), PerfilResponse(
            id=u["id"],
            user_id=u["user_id"],
            nombre_completo=u["nombre_completo"],
            email=u["email"],
            telefono=u.get("telefono"),
            tipo_cliente=u.get("tipo_cliente", "retail"),
            role=u["role"],
            sucursal_id=u.get("sucursal_id"),
            puntos_saldo=u.get("puntos_saldo", 50)
        ))

    # Fallback desde claims del token
    return PerfilResponse(
        id=uuid.UUID(user_id) if user_id else uuid.uuid4(),
        nombre_completo=current_user.get("nombre_completo") or "Usuario MaxiConecta",
        email=email or "usuario@maxiconecta.bo",
        role=current_user.get("role", "cliente"),
        sucursal_id=current_user.get("sucursal_id"),
        puntos_saldo=50
    )


@router.post("/auth/refresh", response_model=TokenResponse)
async def refrescar_token(payload: RefreshTokenRequest):
    """
    Renueva el token de acceso JWT utilizando el refresh token.
    """
    decoded = decode_access_token(payload.refresh_token)
    if not decoded or decoded.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de refresco inválido o expirado"
        )

    email = decoded.get("email", "").lower()
    user_record = _USERS_DB.get(email)
    if not user_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario asociado al token no encontrado"
        )

    cid = str(user_record["id"])
    perfil = _CLIENTES_DB.get(cid, PerfilResponse(
        id=user_record["id"],
        user_id=user_record.get("user_id"),
        nombre_completo=user_record["nombre_completo"],
        email=user_record["email"],
        role=user_record["role"],
        sucursal_id=user_record.get("sucursal_id"),
        puntos_saldo=user_record.get("puntos_saldo", 50)
    ))
    return _create_token_response(user_record, perfil)


# ------------------------------------------------------------------------------
# GESTIÓN DE PERFILES Y DIRECCIONES (RF-23, RF-25, RF-26)
# ------------------------------------------------------------------------------

@router.get("/{cliente_id}", response_model=PerfilResponse)
async def obtener_perfil(cliente_id: uuid.UUID):
    """RF-23: Consultar perfil personal por ID."""
    cid = str(cliente_id)
    if cid in _CLIENTES_DB:
        return _CLIENTES_DB[cid]
    return PerfilResponse(
        id=cliente_id,
        nombre_completo="Cliente Demo MaxiConecta",
        email="cliente.demo@maxiconecta.bo",
        telefono="+591 70012345",
        role="cliente",
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
    cid_str = str(cliente_id)
    if cid_str not in _DIRECCIONES_DB:
        _DIRECCIONES_DB[cid_str] = []
    _DIRECCIONES_DB[cid_str].append(direccion)
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
    cid = str(cliente_id)
    saldo = 120
    if cid in _CLIENTES_DB:
        saldo = _CLIENTES_DB[cid].puntos_saldo
    return {"cliente_id": cliente_id, "puntos_saldo": saldo}
