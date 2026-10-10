import sys
import os
import uuid
from decimal import Decimal
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from fastapi.testclient import TestClient
from backend.services.pos.app.main import app as pos_app
from backend.shared.security import create_access_token

client = TestClient(pos_app)

def test_listar_pedidos_click_and_collect():
    """KAN-324: Listar pedidos Click & Collect para mostrador."""
    resp = client.get("/api/v1/pos/click-and-collect/pedidos")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 2
    codigos = [p["codigo_retiro"] for p in data]
    assert "RET-789214" in codigos


def test_validar_codigo_retiro_exitoso():
    """KAN-324 / KAN-108: Validar código de retiro y estado entregable."""
    resp = client.post("/api/v1/pos/click-and-collect/validar", json={
        "codigo": "RET-789214",
        "sucursal_id": "SUC-01"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["codigo_retiro"] == "RET-789214"
    assert data["codigo_orden"] == "ORD-2026-CC101"
    assert data["estado"] == "confirmada"
    assert data["es_entregable"] is True
    assert data["cliente_nombre"] == "Carlos Mendoza Patzi"
    assert len(data["items"]) >= 2
    assert float(data["total"]) == 15766.00


def test_validar_qr_click_and_collect():
    """KAN-324: Validar lectura de código QR compuesto."""
    payload_qr = "MAXI-CC|ORD-2026-CC101|RET-789214|SUC-01"
    resp = client.post("/api/v1/pos/click-and-collect/validar", json={
        "codigo": payload_qr
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["codigo_retiro"] == "RET-789214"
    assert data["es_entregable"] is True


def test_validar_codigo_ya_entregado():
    """KAN-108: Validación de pedido ya entregado con auditoría previa."""
    resp = client.post("/api/v1/pos/click-and-collect/validar", json={
        "codigo": "RET-345091"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["estado"] == "entregada"
    assert data["es_entregable"] is False
    assert "YA FUE ENTREGADO" in (data["motivo_rechazo"] or "")
    assert data["despacho"] is not None
    assert data["despacho"]["receptor_nombre"] == "Roberto Doria Medina"


def test_validar_codigo_cancelado():
    """KAN-108: Validación de pedido cancelado."""
    resp = client.post("/api/v1/pos/click-and-collect/validar", json={
        "codigo": "RET-992381"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["estado"] == "cancelada"
    assert data["es_entregable"] is False
    assert "CANCELADO" in (data["motivo_rechazo"] or "")


def test_validar_codigo_inexistente():
    """KAN-324: Código no encontrado retorna 404."""
    resp = client.post("/api/v1/pos/click-and-collect/validar", json={
        "codigo": "RET-INVALIDO-999"
    })
    assert resp.status_code == 404


def test_confirmar_entrega_click_and_collect():
    """KAN-325: Actualización a 'entregada' y registro de auditoría de despacho."""
    cajero_token = create_access_token({"sub": "cajero-001", "role": "cajero"})
    headers = {"Authorization": f"Bearer {cajero_token}"}

    payload = {
        "orden_id": "3b749d44-0db0-4e36-9694-84c1724490f1",
        "codigo_retiro": "RET-789214",
        "receptor_nombre": "Carlos Mendoza Patzi",
        "receptor_documento": "4829102",
        "receptor_tipo": "titular",
        "receptor_telefono": "+591 71234567",
        "observaciones": "Mercadería entregada en perfectas condiciones con caja sellada.",
        "cajero_id": "cajero-001",
        "cajero_nombre": "Oscar Menacho",
        "sucursal_id": "SUC-01",
        "sucursal_nombre": "Sucursal Central - La Paz"
    }

    resp = client.post("/api/v1/pos/click-and-collect/confirmar-entrega", json=payload, headers=headers)
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["success"] is True
    assert res_data["nuevo_estado"] == "entregada"
    assert res_data["receptor_nombre"] == "Carlos Mendoza Patzi"
    assert "comprobante_entrega" in res_data
    assert res_data["comprobante_entrega"]["codigo_orden"] == "ORD-2026-CC101"

    # Segunda validación: ahora debe reflejar que ya fue entregado
    resp_val = client.post("/api/v1/pos/click-and-collect/validar", json={"codigo": "RET-789214"})
    assert resp_val.status_code == 200
    val_data = resp_val.json()
    assert val_data["estado"] == "entregada"
    assert val_data["es_entregable"] is False


def test_confirmar_entrega_rechazada_si_ya_entregada():
    """KAN-325: No se puede confirmar una entrega ya realizada."""
    cajero_token = create_access_token({"sub": "cajero-001", "role": "cajero"})
    headers = {"Authorization": f"Bearer {cajero_token}"}

    payload = {
        "orden_id": "c56b06e9-bfe9-4e7a-9a99-8ee3ad192305",
        "codigo_retiro": "RET-345091",
        "receptor_nombre": "Otro Receptor",
        "receptor_documento": "998877",
        "receptor_tipo": "tercero_autorizado"
    }

    resp = client.post("/api/v1/pos/click-and-collect/confirmar-entrega", json=payload, headers=headers)
    assert resp.status_code == 400
    assert "ya fue entregado" in resp.json()["detail"].lower()
