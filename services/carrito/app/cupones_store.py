"""
Persistencia de cupones (RF-17).

Usa la tabla ``cupones`` de Supabase (db/schema.sql) cuando hay credenciales
configuradas; si Supabase no está disponible (desarrollo local / pruebas) cae
a un almacén en memoria con los mismos campos, siguiendo el patrón de
degradación del resto de microservicios.
"""
import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from backend.shared.database import get_supabase_admin_client

logger = logging.getLogger("maxiconecta.cupones")

_LOCK = asyncio.Lock()
_MEMORIA: Dict[str, Dict[str, Any]] = {}


def _semilla() -> Dict[str, Dict[str, Any]]:
    ahora = datetime.now(timezone.utc)
    base = [
        dict(codigo="MAXI10", descripcion="10% de descuento en toda la tienda", tipo_descuento="porcentaje",
             valor_descuento=10, monto_minimo=0, usos_maximos=1000, usos_actuales=0,
             fecha_inicio=ahora - timedelta(days=1), fecha_fin=None, activo=True),
        dict(codigo="BIENVENIDO", descripcion="Bs. 20 de descuento en tu primera compra", tipo_descuento="monto_fijo",
             valor_descuento=20, monto_minimo=100, usos_maximos=500, usos_actuales=0,
             fecha_inicio=ahora - timedelta(days=1), fecha_fin=None, activo=True),
        dict(codigo="VIP20", descripcion="20% para clientes VIP (compra mínima Bs. 500)", tipo_descuento="porcentaje",
             valor_descuento=20, monto_minimo=500, usos_maximos=100, usos_actuales=0,
             fecha_inicio=ahora - timedelta(days=1), fecha_fin=ahora + timedelta(days=90), activo=True),
    ]
    return {c["codigo"]: {"id": str(uuid.uuid4()), **c} for c in base}


def reiniciar_memoria() -> None:
    """Restaura el almacén en memoria a su estado semilla (útil en pruebas)."""
    _MEMORIA.clear()
    _MEMORIA.update(_semilla())


reiniciar_memoria()


def _supabase() -> Optional[Any]:
    try:
        return get_supabase_admin_client()
    except Exception as exc:  # pragma: no cover - depende del entorno
        logger.warning("Supabase no disponible para cupones: %s", exc)
        return None


def _normalizar_fila(fila: Dict[str, Any]) -> Dict[str, Any]:
    fila = dict(fila)
    fila["codigo"] = str(fila["codigo"]).upper()
    return fila


async def listar() -> List[Dict[str, Any]]:
    client = _supabase()
    if client:
        try:
            res = client.table("cupones").select("*").order("codigo").execute()
            return [_normalizar_fila(r) for r in (res.data or [])]
        except Exception as exc:
            logger.warning("Error listando cupones en Supabase (se usa memoria): %s", exc)
    return sorted((dict(c) for c in _MEMORIA.values()), key=lambda c: c["codigo"])


async def obtener(codigo: str) -> Optional[Dict[str, Any]]:
    codigo = codigo.strip().upper()
    client = _supabase()
    if client:
        try:
            res = client.table("cupones").select("*").eq("codigo", codigo).limit(1).execute()
            if res.data:
                return _normalizar_fila(res.data[0])
            return None
        except Exception as exc:
            logger.warning("Error consultando cupón en Supabase (se usa memoria): %s", exc)
    cupon = _MEMORIA.get(codigo)
    return dict(cupon) if cupon else None


def _serializar(datos: Dict[str, Any]) -> Dict[str, Any]:
    salida = {}
    for clave, valor in datos.items():
        if isinstance(valor, datetime):
            salida[clave] = valor.isoformat()
        elif hasattr(valor, "as_tuple"):  # Decimal -> float para JSON/PostgREST
            salida[clave] = float(valor)
        else:
            salida[clave] = valor
    return salida


async def crear(datos: Dict[str, Any]) -> Dict[str, Any]:
    datos = dict(datos)
    datos["codigo"] = datos["codigo"].strip().upper()
    datos.setdefault("usos_actuales", 0)
    client = _supabase()
    if client:
        try:
            res = client.table("cupones").insert(_serializar(datos)).execute()
            if res.data:
                return _normalizar_fila(res.data[0])
        except Exception as exc:
            logger.warning("Error creando cupón en Supabase (se usa memoria): %s", exc)
    async with _LOCK:
        registro = {"id": str(uuid.uuid4()), **datos}
        _MEMORIA[datos["codigo"]] = registro
        return dict(registro)


async def actualizar(codigo: str, cambios: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    codigo = codigo.strip().upper()
    client = _supabase()
    if client:
        try:
            res = client.table("cupones").update(_serializar(cambios)).eq("codigo", codigo).execute()
            if res.data:
                return _normalizar_fila(res.data[0])
            return None
        except Exception as exc:
            logger.warning("Error actualizando cupón en Supabase (se usa memoria): %s", exc)
    async with _LOCK:
        if codigo not in _MEMORIA:
            return None
        _MEMORIA[codigo].update(cambios)
        return dict(_MEMORIA[codigo])


async def eliminar(codigo: str) -> bool:
    codigo = codigo.strip().upper()
    client = _supabase()
    if client:
        try:
            res = client.table("cupones").delete().eq("codigo", codigo).execute()
            return bool(res.data)
        except Exception as exc:
            logger.warning("Error eliminando cupón en Supabase (se usa memoria): %s", exc)
    async with _LOCK:
        return _MEMORIA.pop(codigo, None) is not None


async def incrementar_uso(codigo: str, usos_esperados: int) -> bool:
    """
    Suma un canje de forma atómica. ``usos_esperados`` es el contador leído al
    validar: si otro canje ocurrió entremedio, el incremento se rechaza
    (concurrencia optimista) para no superar ``usos_maximos``.
    """
    codigo = codigo.strip().upper()
    client = _supabase()
    if client:
        try:
            res = (
                client.table("cupones")
                .update({"usos_actuales": usos_esperados + 1})
                .eq("codigo", codigo)
                .eq("usos_actuales", usos_esperados)
                .execute()
            )
            return bool(res.data)
        except Exception as exc:
            logger.warning("Error incrementando uso de cupón en Supabase (se usa memoria): %s", exc)
    async with _LOCK:
        cupon = _MEMORIA.get(codigo)
        if not cupon or int(cupon.get("usos_actuales") or 0) != usos_esperados:
            return False
        cupon["usos_actuales"] = usos_esperados + 1
        return True
