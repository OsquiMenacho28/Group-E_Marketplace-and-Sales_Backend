"""
Pruebas integrales de extremo a extremo para validar todos los módulos integrados:
- Michelle: KAN-112 Suspensión y reanudación de ventas en caja POS.
- Osqui: RF-07 Stock con caché Redis, RF-08 SSE & Delta sync, Búsqueda multi-sucursal (F3).
- Alex: Carrito PUT para actualización de cantidades persistente, cupones de descuento.
- Kevin: Timbrado fiscal CUF (RIO-PAG-02), apertura/cierre de cajas y esquemas fiscales.
- Gateway: API Gateway health y validación de reglas RBAC.
"""
import sys
import os
import uuid
from decimal import Decimal

# Asegurar path de importación del backend
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from fastapi.testclient import TestClient
from backend.services.pos.app.main import app as pos_app
from backend.services.catalogo.app.main import app as catalogo_app
from backend.services.carrito.app.main import app as carrito_app
from backend.services.clientes.app.main import app as clientes_app
from backend.gateway.app.main import app as gateway_app
from backend.shared.security import create_access_token

pos_client = TestClient(pos_app)
catalogo_client = TestClient(catalogo_app)
carrito_client = TestClient(carrito_app)
clientes_client = TestClient(clientes_app)
gateway_client = TestClient(gateway_app)

def test_pos_suspension_ventas_michelle():
    """Valida el flujo de KAN-112: suspender, listar y reanudar ventas en espera."""
    venta_id = f"susp-{uuid.uuid4().hex[:8]}"
    payload_suspender = {
        "id": venta_id,
        "cliente_referencia": "Carlos Zambrana",
        "items": [
            {
                "variante_id": str(uuid.uuid4()),
                "sku": "LAP-DELL-XPS15",
                "nombre": "Laptop Dell XPS 15",
                "cantidad": 1,
                "precio_unitario": 8999.00
            }
        ],
        "subtotal": 8999.00
    }

    # 1. Suspender venta
    resp_susp = pos_client.post("/api/v1/pos/ventas/suspender", json=payload_suspender)
    assert resp_susp.status_code == 201, f"Error al suspender: {resp_susp.text}"
    assert resp_susp.json()["id"] == venta_id

    # 2. Listar ventas suspendidas
    resp_list = pos_client.get("/api/v1/pos/ventas/suspendidas")
    assert resp_list.status_code == 200
    ventas = resp_list.json()
    encontrada = any(v["id"] == venta_id for v in ventas)
    assert encontrada, f"La venta suspendida {venta_id} no apareció en el listado"

    # 3. Reanudar (quitar de espera)
    resp_del = pos_client.delete(f"/api/v1/pos/ventas/suspendidas/{venta_id}")
    assert resp_del.status_code == 200
    venta_reanudada = resp_del.json()
    assert venta_reanudada["id"] == venta_id

    # 4. Verificar que ya no está en espera
    resp_list_after = pos_client.get("/api/v1/pos/ventas/suspendidas")
    assert all(v["id"] != venta_id for v in resp_list_after.json())


def test_catalogo_stock_multisucursal_osqui():
    """Valida RF-07 stock con caché Redis y búsqueda multi-sucursal (F3)."""
    # 1. Consultar stock individual por SKU
    resp_stock = catalogo_client.get("/api/v1/catalogo/stock/LAP-DELL-XPS15")
    assert resp_stock.status_code == 200
    stock_data = resp_stock.json()
    assert stock_data["sku"] == "LAP-DELL-XPS15"
    assert stock_data["stock_disponible"] > 0
    assert stock_data["origen"] in ["erp", "cache"]

    # 2. Segunda consulta debe servirse desde caché
    resp_stock_cache = catalogo_client.get("/api/v1/catalogo/stock/LAP-DELL-XPS15")
    assert resp_stock_cache.status_code == 200
    assert resp_stock_cache.json()["origen"] == "cache"

    # 3. Búsqueda multi-sucursal rápida (modal F3)
    resp_multi = catalogo_client.get("/api/v1/catalogo/productos/buscar-stock?q=Dell")
    assert resp_multi.status_code == 200
    multi_data = resp_multi.json()
    assert "resultados" in multi_data
    assert len(multi_data["resultados"]) > 0
    primero = multi_data["resultados"][0]
    assert "sucursales" in primero
    assert len(primero["sucursales"]) > 0

    # 4. Delta de sincronización de catálogo (RF-08)
    resp_sync = catalogo_client.get("/api/v1/catalogo/sync-catalogo")
    assert resp_sync.status_code == 200
    sync_data = resp_sync.json()
    assert "items" in sync_data
    assert len(sync_data["items"]) > 0
    assert "servidor_timestamp" in sync_data


def test_carrito_actualizar_cantidad_alex():
    """Valida endpoint PUT de Alex para modificar cantidad y persistir en Redis."""
    cliente_id = f"test-cart-{uuid.uuid4().hex[:8]}"
    var_id = str(uuid.uuid4())

    # 1. Agregar ítem inicial (cantidad: 2)
    resp_add = carrito_client.post(f"/api/v1/carrito/{cliente_id}/items", json={
        "variante_id": var_id,
        "sku": "TEC-LOGI-MXM3S",
        "nombre": "Mouse Logitech MX Master 3S",
        "cantidad": 2,
        "precio_unitario": 699.00
    })
    assert resp_add.status_code == 200
    assert float(resp_add.json()["subtotal"]) == 1398.00

    # 2. Actualizar cantidad a 5 vía PUT (Alex branch)
    resp_update = carrito_client.put(f"/api/v1/carrito/{cliente_id}/items/{var_id}", json={
        "cantidad": 5
    })
    assert resp_update.status_code == 200
    cart_data = resp_update.json()
    assert float(cart_data["subtotal"]) == 3495.00
    assert cart_data["items"][0]["cantidad"] == 5

    # 3. Aplicar cupón MAXI10 (10% descuento)
    resp_cupon = carrito_client.post(f"/api/v1/carrito/{cliente_id}/cupon", json={
        "codigo": "MAXI10"
    })
    assert resp_cupon.status_code == 200
    cupon_data = resp_cupon.json()
    assert float(cupon_data["descuento_cupon"]) == 349.50
    assert float(cupon_data["total"]) == 3145.50


def test_pos_caja_y_facturacion_cuf_kevin():
    """Valida apertura de caja, venta con emisión fiscal CUF (RIO-PAG-02) y cierre de caja."""
    # Generar token JWT con rol cajero
    token_cajero = create_access_token(
        data={"sub": str(uuid.uuid4()), "role": "cajero", "sucursal_id": "sucursal-central-001"}
    )
    headers = {"Authorization": f"Bearer {token_cajero}"}

    # 1. Apertura de caja
    sucursal_id = uuid.uuid4()
    cajero_id = uuid.uuid4()
    resp_abrir = pos_client.post("/api/v1/pos/caja/abrir", json={
        "sucursal_id": str(sucursal_id),
        "cajero_id": str(cajero_id),
        "fondo_inicial": 200.00
    }, headers=headers)
    assert resp_abrir.status_code == 201
    caja_id = resp_abrir.json()["id"]

    # 2. Cobrar venta presencial con NIT y Razón Social (Timbrado CUF)
    resp_cobrar = pos_client.post("/api/v1/pos/ventas/cobrar", json={
        "caja_id": caja_id,
        "sucursal_id": str(sucursal_id),
        "cliente_nit_ci": "1029384756",
        "cliente_razon_social": "Constructora Los Andes S.R.L.",
        "metodo_pago": "efectivo",
        "items": [
            {
                "variante_id": str(uuid.uuid4()),
                "sku": "MON-LG-27GP850",
                "nombre": "Monitor Gamer LG UltraGear 27",
                "cantidad": 1,
                "precio_unitario": 2899.00
            }
        ]
    }, headers=headers)
    assert resp_cobrar.status_code == 201
    venta_data = resp_cobrar.json()
    assert float(venta_data["total"]) == 2899.00
    assert "cuf" in venta_data and venta_data["cuf"] is not None
    assert "numero_factura" in venta_data and venta_data["numero_factura"] is not None
    assert "ticket_impresion" in venta_data

    # 3. Cierre de caja y arqueo
    resp_cerrar = pos_client.post(f"/api/v1/pos/caja/{caja_id}/cerrar", json={
        "monto_cierre_real": 3099.00 # 200 fondo + 2899 venta
    })
    assert resp_cerrar.status_code == 200
    cierre_data = resp_cerrar.json()
    assert cierre_data["estado"] == "cerrada"
    assert float(cierre_data["diferencia"]) == 0.00


def test_gateway_health_and_rbac():
    """Valida la operatividad del API Gateway y sus políticas RBAC."""
    # 1. Health check
    resp_health = gateway_client.get("/health")
    assert resp_health.status_code == 200
    health_data = resp_health.json()
    assert health_data["status"] == "healthy"
    assert "catalogo" in health_data["microservices"]
    assert "pos" in health_data["microservices"]

    # 2. RBAC: Intento de entrar a POS sin credenciales debe dar 401
    resp_unauth = gateway_client.get("/api/v1/pos/ventas/suspendidas")
    assert resp_unauth.status_code == 401


def test_catalogo_resolucion_precios_michelle():
    """Valida KAN-297: resolución dinámica de precios según canal y tipo de cliente."""
    variante_test_id = str(uuid.uuid4())
    resp = catalogo_client.get(
        f"/api/v1/catalogo/precios/resolver?variante_id={variante_test_id}&canal=pos&tipo_cliente=retail"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["canal"] == "pos"
    assert data["tipo_cliente"] == "retail"
    assert "precio" in data and float(data["precio"]) > 0
    assert data["moneda"] == "BOB"

