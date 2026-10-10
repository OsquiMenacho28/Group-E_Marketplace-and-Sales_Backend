"""
Motor de validación y cálculo de descuento de cupones (RF-17).

Es una función pura (sin I/O) para poder probarla de forma aislada: recibe el
cupón tal como se guarda en la tabla ``cupones`` (mismos nombres de columna),
el subtotal del carrito y la fecha actual, y devuelve si el cupón es aplicable,
el motivo del rechazo (con un mensaje apto para mostrar al cliente) y el
descuento calculado en bolivianos.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, Optional

TIPO_PORCENTAJE = "porcentaje"
TIPO_MONTO_FIJO = "monto_fijo"

_DOS_DECIMALES = Decimal("0.01")


@dataclass(frozen=True)
class ResultadoCupon:
    valido: bool
    codigo: str
    motivo: Optional[str] = None  # NO_EXISTE | INACTIVO | AUN_NO_VIGENTE | VENCIDO | MONTO_MINIMO | LIMITE_CANJES
    mensaje: str = ""
    descuento: Decimal = Decimal("0.00")
    tipo_descuento: Optional[str] = None
    valor_descuento: Optional[Decimal] = None
    monto_minimo: Decimal = Decimal("0.00")


def _a_decimal(valor: Any, por_defecto: str = "0") -> Decimal:
    if valor is None or valor == "":
        return Decimal(por_defecto)
    return Decimal(str(valor))


def _a_fecha(valor: Any) -> Optional[datetime]:
    """Normaliza fechas ISO / datetime a datetime con zona horaria UTC."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, datetime):
        fecha = valor
    else:
        fecha = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    return fecha if fecha.tzinfo else fecha.replace(tzinfo=timezone.utc)


def redondear(monto: Decimal) -> Decimal:
    return monto.quantize(_DOS_DECIMALES, rounding=ROUND_HALF_UP)


def calcular_descuento(tipo_descuento: str, valor_descuento: Decimal, subtotal: Decimal) -> Decimal:
    """Descuento porcentual o de monto fijo; nunca supera el subtotal."""
    if subtotal <= 0:
        return Decimal("0.00")
    if tipo_descuento == TIPO_PORCENTAJE:
        bruto = subtotal * valor_descuento / Decimal("100")
    else:
        bruto = valor_descuento
    return redondear(min(bruto, subtotal))


def evaluar_cupon(
    cupon: Optional[Dict[str, Any]],
    subtotal: Decimal,
    ahora: Optional[datetime] = None,
    codigo_solicitado: str = "",
) -> ResultadoCupon:
    """Valida el cupón contra vigencia, activación, monto mínimo y límite de canjes."""
    ahora = ahora or datetime.now(timezone.utc)
    subtotal = _a_decimal(subtotal)

    if not cupon:
        return ResultadoCupon(
            valido=False,
            codigo=codigo_solicitado,
            motivo="NO_EXISTE",
            mensaje="El cupón ingresado no existe.",
        )

    codigo = str(cupon.get("codigo") or codigo_solicitado).upper()
    tipo = cupon.get("tipo_descuento")
    valor = _a_decimal(cupon.get("valor_descuento"))
    minimo = _a_decimal(cupon.get("monto_minimo"))
    base = dict(codigo=codigo, tipo_descuento=tipo, valor_descuento=valor, monto_minimo=minimo)

    if not cupon.get("activo", True):
        return ResultadoCupon(valido=False, motivo="INACTIVO", mensaje="Este cupón no está activo.", **base)

    inicio = _a_fecha(cupon.get("fecha_inicio"))
    if inicio and ahora < inicio:
        return ResultadoCupon(
            valido=False,
            motivo="AUN_NO_VIGENTE",
            mensaje=f"Este cupón estará vigente desde el {inicio.strftime('%d/%m/%Y')}.",
            **base,
        )

    fin = _a_fecha(cupon.get("fecha_fin"))
    if fin and ahora > fin:
        return ResultadoCupon(
            valido=False,
            motivo="VENCIDO",
            mensaje=f"Este cupón venció el {fin.strftime('%d/%m/%Y')}.",
            **base,
        )

    usos_maximos = cupon.get("usos_maximos")
    usos_actuales = int(cupon.get("usos_actuales") or 0)
    if usos_maximos is not None and usos_actuales >= int(usos_maximos):
        return ResultadoCupon(
            valido=False,
            motivo="LIMITE_CANJES",
            mensaje="Este cupón alcanzó su límite de canjes.",
            **base,
        )

    if subtotal < minimo:
        faltante = redondear(minimo - subtotal)
        return ResultadoCupon(
            valido=False,
            motivo="MONTO_MINIMO",
            mensaje=f"Compra mínima de Bs. {redondear(minimo)} para usar este cupón (te faltan Bs. {faltante}).",
            **base,
        )

    descuento = calcular_descuento(str(tipo), valor, subtotal)
    etiqueta = f"{valor.normalize():f}%" if tipo == TIPO_PORCENTAJE else f"Bs. {redondear(valor)}"
    return ResultadoCupon(
        valido=True,
        motivo=None,
        mensaje=f"¡Cupón {codigo} aplicado! Ahorras Bs. {descuento} ({etiqueta} de descuento).",
        descuento=descuento,
        **base,
    )
