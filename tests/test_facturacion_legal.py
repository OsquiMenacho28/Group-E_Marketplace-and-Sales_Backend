import sys
import os
import uuid
from decimal import Decimal
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from fastapi.testclient import TestClient
from backend.services.ordenes.app.main import app as ordenes_app
from backend.shared.security import create_access_token

client = TestClient(ordenes_app)

def test_validar_nit_consumidor_final():
    resp = client.post("/api/v1/facturacion/validar-nit", json={"nit_ci": "0", "tipo_documento": "CI"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["valido"] is True
    assert data["razon_social"] == "CONSUMIDOR FINAL"

def test_validar_nit_empresa_padron():
    resp = client.post("/api/v1/facturacion/validar-nit", json={"nit_ci": "1020304050", "tipo_documento": "NIT"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["valido"] is True
    assert "SAN CRIST" in data["razon_social"]

def test_emitir_factura_legal_cuf():
    resp = client.post("/api/v1/facturacion/emitir", json={
        "modalidad": "con_factura",
        "tipo_documento": "NIT",
        "nit_ci": "1020304050",
        "razon_social": "EMPRESA MINERA SAN CRISTOBAL S.A.",
        "email_facturacion": "contabilidad@sancristobal.bo",
        "guardar_perfil": True,
        "sucursal": "Sucursal Sopocachi",
        "punto_venta": 1,
        "metodo_pago": "qr",
        "items": [
            {
                "sku": "KEY-RGB-01",
                "nombre": "Teclado Mecanico RGB",
                "cantidad": 2,
                "precio_unitario": 250.00
            }
        ],
        "descuento": 0
    })
    assert resp.status_code == 201
    res_data = resp.json()
    fac = res_data["factura"]
    assert "cuf" in fac and fac["cuf"].startswith("CUF-")
    assert "cufd" in fac and fac["cufd"].startswith("CUFD-")
    assert fac["total"] == 500.00
    assert fac["monto_iva"] == 65.00 # 13% de 500
    assert "pilotosiat.impuestos.gob.bo" in fac["codigo_qr"]

def test_crear_orden_con_datos_fiscales():
    token = create_access_token({"sub": str(uuid.uuid4()), "role": "cliente"})
    resp = client.post("/api/v1/ordenes/", json={
        "cliente_id": "cliente-marketplace-demo",
        "canal": "web",
        "tipo_despacho": "domicilio",
        "subtotal": 600.00,
        "descuento": 0.00,
        "costo_envio": 15.00,
        "total": 615.00,
        "metodo_pago": "tarjeta",
        "items": [
            {
                "variante_id": str(uuid.uuid4()),
                "sku": "MOUSE-LOGI-MX",
                "nombre_producto": "Mouse Logitech MX Master",
                "cantidad": 1,
                "precio_unitario": 600.00
            }
        ],
        "datos_fiscales": {
            "modalidad": "con_factura",
            "tipo_documento": "NIT",
            "nit_ci": "1002345678",
            "razon_social": "MAXICONECTA BOLIVIA S.R.L.",
            "email_facturacion": "facturacion@maxiconecta.bo"
        }
    }, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 201
    data = resp.json()
    assert "cuf_factura" in data and data["cuf_factura"].startswith("CUF-")
    assert data["factura"]["numero_factura"] is not None
    assert data["factura"]["datos_comprador"]["nit_ci"] == "1002345678"
