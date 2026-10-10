"""
RF-17 — Promociones y Cupones.

* Cliente (público): validar un cupón contra el subtotal y canjearlo.
* Administrador / Gerente Comercial: alta, edición, activación y baja de cupones.
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status

try:
    from app import cupones_store
    from app.cupones_engine import evaluar_cupon, redondear, _a_fecha
    from app.schemas import (
        CuponAdminCreate, CuponAdminUpdate, CuponAdminResponse,
        ValidarCuponRequest, ValidarCuponResponse,
    )
except (ModuleNotFoundError, ImportError):
    from backend.services.carrito.app import cupones_store
    from backend.services.carrito.app.cupones_engine import evaluar_cupon, redondear, _a_fecha
    from backend.services.carrito.app.schemas import (
        CuponAdminCreate, CuponAdminUpdate, CuponAdminResponse,
        ValidarCuponRequest, ValidarCuponResponse,
    )
from backend.shared.security import get_current_user, require_jwt_claims

router = APIRouter(prefix="/api/v1/carrito", tags=["Promociones y Cupones"])

ROLES_ADMIN = {"administrador", "gerente_comercial"}


def _estado_vigencia(cupon: Dict[str, Any]) -> str:
    ahora = datetime.now(timezone.utc)
    if not cupon.get("activo", True):
        return "inactivo"
    maximos = cupon.get("usos_maximos")
    if maximos is not None and int(cupon.get("usos_actuales") or 0) >= int(maximos):
        return "agotado"
    inicio, fin = _a_fecha(cupon.get("fecha_inicio")), _a_fecha(cupon.get("fecha_fin"))
    if inicio and ahora < inicio:
        return "programado"
    if fin and ahora > fin:
        return "vencido"
    return "vigente"


def _a_respuesta(cupon: Dict[str, Any]) -> CuponAdminResponse:
    return CuponAdminResponse(**{**cupon, "estado_vigencia": _estado_vigencia(cupon)})


def _a_validacion(resultado, subtotal: Decimal) -> ValidarCuponResponse:
    return ValidarCuponResponse(
        valido=resultado.valido,
        codigo=resultado.codigo,
        motivo=resultado.motivo,
        mensaje=resultado.mensaje,
        descuento=resultado.descuento,
        tipo_descuento=resultado.tipo_descuento,
        valor_descuento=resultado.valor_descuento,
        monto_minimo=resultado.monto_minimo,
        total_con_descuento=redondear(max(Decimal("0"), subtotal - resultado.descuento)),
    )


# ------------------------------------------------------------------------------
# Cliente: validar / canjear (feedback inmediato de ahorro)
# ------------------------------------------------------------------------------
@router.post("/validar-cupon", response_model=ValidarCuponResponse)
async def validar_cupon(payload: ValidarCuponRequest):
    """Valida el cupón contra el subtotal actual y calcula el ahorro (no consume el cupón)."""
    codigo = payload.codigo.strip().upper()
    cupon = await cupones_store.obtener(codigo)
    resultado = evaluar_cupon(cupon, payload.subtotal, codigo_solicitado=codigo)
    return _a_validacion(resultado, payload.subtotal)


@router.post("/canjear-cupon", response_model=ValidarCuponResponse)
async def canjear_cupon(payload: ValidarCuponRequest):
    """Consume un canje del cupón al confirmarse la compra (revalida y respeta el límite de canjes)."""
    codigo = payload.codigo.strip().upper()
    cupon = await cupones_store.obtener(codigo)
    resultado = evaluar_cupon(cupon, payload.subtotal, codigo_solicitado=codigo)
    if not resultado.valido:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=resultado.mensaje)
    registrado = await cupones_store.incrementar_uso(codigo, int(cupon.get("usos_actuales") or 0))
    if not registrado:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El cupón fue canjeado por otra compra al mismo tiempo. Inténtalo nuevamente.",
        )
    return _a_validacion(resultado, payload.subtotal)


# ------------------------------------------------------------------------------
# Administración: gestión y activación de promociones
# ------------------------------------------------------------------------------
@router.get("/cupones", response_model=List[CuponAdminResponse])
@require_jwt_claims("sub", allowed_roles=ROLES_ADMIN)
async def listar_cupones(current_user: Dict[str, Any] = Depends(get_current_user)):
    return [_a_respuesta(c) for c in await cupones_store.listar()]


@router.post("/cupones", response_model=CuponAdminResponse, status_code=status.HTTP_201_CREATED)
@require_jwt_claims("sub", allowed_roles=ROLES_ADMIN)
async def crear_cupon(payload: CuponAdminCreate, current_user: Dict[str, Any] = Depends(get_current_user)):
    codigo = payload.codigo.strip().upper()
    if await cupones_store.obtener(codigo):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Ya existe un cupón con el código {codigo}.")
    datos = payload.model_dump()
    datos["codigo"] = codigo
    datos["fecha_inicio"] = datos["fecha_inicio"] or datetime.now(timezone.utc)
    return _a_respuesta(await cupones_store.crear(datos))


@router.get("/cupones/{codigo}", response_model=CuponAdminResponse)
@require_jwt_claims("sub", allowed_roles=ROLES_ADMIN)
async def obtener_cupon(codigo: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    cupon = await cupones_store.obtener(codigo)
    if not cupon:
        raise HTTPException(status_code=404, detail="Cupón no encontrado")
    return _a_respuesta(cupon)


@router.patch("/cupones/{codigo}", response_model=CuponAdminResponse)
@require_jwt_claims("sub", allowed_roles=ROLES_ADMIN)
async def actualizar_cupon(
    codigo: str,
    payload: CuponAdminUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Edita un cupón; con ``{"activo": false|true}`` se desactiva o activa la promoción."""
    cupon = await cupones_store.obtener(codigo)
    if not cupon:
        raise HTTPException(status_code=404, detail="Cupón no encontrado")
    cambios = payload.model_dump(exclude_unset=True)
    if not cambios:
        raise HTTPException(status_code=400, detail="No se enviaron campos para actualizar")

    fusion = {**cupon, **cambios}
    if fusion.get("tipo_descuento") == "porcentaje" and Decimal(str(fusion["valor_descuento"])) > 100:
        raise HTTPException(status_code=422, detail="Un descuento porcentual no puede superar el 100%")
    actualizado = await cupones_store.actualizar(codigo, cambios)
    return _a_respuesta(actualizado)


@router.delete("/cupones/{codigo}", status_code=status.HTTP_204_NO_CONTENT)
@require_jwt_claims("sub", allowed_roles=ROLES_ADMIN)
async def eliminar_cupon(codigo: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    if not await cupones_store.eliminar(codigo):
        raise HTTPException(status_code=404, detail="Cupón no encontrado")
    return None
