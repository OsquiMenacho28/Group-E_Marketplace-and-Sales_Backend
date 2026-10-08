import base64
import pathlib
import sys
import uuid

from fastapi.testclient import TestClient

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "pos"))

from backend.services.pos.app import routers as pos_routers
from backend.services.pos.app.main import app
from backend.shared.security import create_access_token


def test_ticket_pos_detalle_iva_cuf_y_qr(monkeypatch):
    async def emitir_factura(datos_fiscales):
        assert len(datos_fiscales["items"]) == 2
        assert datos_fiscales["monto_iva"] == 28.76
        return {"numero_factura": 10099, "cuf": "CUF-TEST-TRIBUTARIO"}

    async def descontar_stock(reserva_id, orden_id):
        return {"status": "DESCONTADO", "modo": "test"}

    monkeypatch.setattr(pos_routers.pagos_client, "emitir_factura", emitir_factura)
    monkeypatch.setattr(pos_routers.inventarios_client, "descuento_definitivo", descontar_stock)

    client = TestClient(app)
    token = create_access_token({"sub": str(uuid.uuid4()), "role": "administrador"})
    headers = {"Authorization": f"Bearer {token}"}
    sucursal_id = str(uuid.uuid4())

    caja = client.post("/api/v1/pos/caja/abrir", headers=headers, json={
        "sucursal_id": sucursal_id,
        "cajero_id": str(uuid.uuid4()),
        "fondo_inicial": 0,
    })
    assert caja.status_code == 201

    venta = client.post("/api/v1/pos/ventas/cobrar", headers=headers, json={
        "caja_id": caja.json()["id"],
        "sucursal_id": sucursal_id,
        "cliente_nit_ci": "0",
        "cliente_razon_social": "CONSUMIDOR FINAL",
        "metodo_pago": "efectivo",
        "items": [
            {"variante_id": str(uuid.uuid4()), "sku": "SKU-1", "nombre": "Producto uno", "cantidad": 2, "precio_unitario": 100},
            {"variante_id": str(uuid.uuid4()), "sku": "SKU-2", "nombre": "Producto dos", "cantidad": 1, "precio_unitario": 50},
        ],
    })

    assert venta.status_code == 201, venta.text
    ticket = venta.json()
    assert float(ticket["total"]) == 250
    assert float(ticket["monto_iva"]) == 28.76
    assert float(ticket["subtotal_neto"]) == 221.24
    assert [float(item["total_linea"]) for item in ticket["items"]] == [200, 50]
    assert ticket["numero_factura"] == 10099
    assert ticket["cuf"] == "CUF-TEST-TRIBUTARIO"
    assert "Producto uno" in ticket["ticket_impresion"]
    assert "IVA (13% incluido): BOB 28.76" in ticket["ticket_impresion"]
    assert "QR tributario:" in ticket["ticket_impresion"]
    assert ticket["qr_url"].startswith("https://pilotosiat.impuestos.gob.bo/consulta/QR?")
    qr_svg = base64.b64decode(ticket["qr_code"].split(",", 1)[1]).decode()
    assert "<svg" in qr_svg
