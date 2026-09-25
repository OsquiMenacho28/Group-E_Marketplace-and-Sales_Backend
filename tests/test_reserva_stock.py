"""
Pruebas automatizadas para US-14 (RF-14 · RIO-INV-02 / RIO-INV-03):
Reserva Temporal de Stock durante el Checkout y Control Concurrente.
Ejecutar con: python backend/tests/test_reserva_stock.py
"""
import sys
import os
import uuid
import asyncio

# Asegurar path de importación
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from fastapi.testclient import TestClient
from backend.services.carrito.app.main import app as carrito_app
from backend.services.ordenes.app.main import app as ordenes_app
from backend.shared.redis_client import (
    crear_reserva_stock, consultar_reserva, liberar_reserva_stock,
    confirmar_reserva_stock, save_cart_to_cache
)

carrito_client = TestClient(carrito_app)
ordenes_client = TestClient(ordenes_app)

def test_reserva_stock_flujo_completo():
    print("=" * 70)
    print("INICIANDO SUITE DE PRUEBAS: US-14 RESERVA TEMPORAL DE STOCK (RF-14)")
    print("=" * 70)

    cliente_id = str(uuid.uuid4())
    variante_id = str(uuid.uuid4())

    # --------------------------------------------------------------------------
    # 1. Preparar carrito con productos
    # --------------------------------------------------------------------------
    print("\n[TEST 1] Preparar carrito con ítem de prueba...")
    item_payload = {
        "variante_id": variante_id,
        "sku": "LAP-DELL-XPS15",
        "nombre": "Laptop Dell XPS 15",
        "cantidad": 1,
        "precio_unitario": 8999.00
    }
    resp_add = carrito_client.post(f"/api/v1/carrito/{cliente_id}/items", json=item_payload)
    assert resp_add.status_code == 200, f"Error al agregar ítem: {resp_add.text}"
    print("  -> OK: Carrito inicializado con éxito en Redis/Memoria")

    # --------------------------------------------------------------------------
    # 2. Iniciar Checkout y Bloquear Stock Temporalmente (RF-14 · RIO-INV-02)
    # --------------------------------------------------------------------------
    print("\n[TEST 2] Iniciar checkout y reservar stock con TTL de 900s (15 min)...")
    checkout_payload = {
        "cliente_id": cliente_id,
        "tipo_despacho": "domicilio",
        "metodo_pago": "qr"
    }
    resp_init = carrito_client.post(f"/api/v1/carrito/{cliente_id}/checkout/iniciar", json=checkout_payload)
    assert resp_init.status_code == 200, f"Error al iniciar checkout: {resp_init.text}"
    data_init = resp_init.json()
    
    reserva_id = data_init["reserva_id"]
    assert reserva_id.startswith("RES-"), f"ID de reserva inválido: {reserva_id}"
    assert data_init["ttl_expira_en_segundos"] == 900
    assert data_init["status"] == "RESERVA_CONFIRMADA"
    assert len(data_init["items_reservados"]) >= 1
    print(f"  -> OK: Stock bloqueado temporalmente con ID '{reserva_id}' y TTL 900s")

    # --------------------------------------------------------------------------
    # 3. Consultar estado y tiempo restante de la reserva en Redis
    # --------------------------------------------------------------------------
    print("\n[TEST 3] Consultar estado de la reserva y segundos restantes...")
    resp_check = carrito_client.get(f"/api/v1/carrito/checkout/reserva/{reserva_id}")
    assert resp_check.status_code == 200, f"Error al consultar reserva: {resp_check.text}"
    data_check = resp_check.json()
    assert data_check["reserva_id"] == reserva_id
    assert data_check["estado"] == "ACTIVA"
    assert 0 < data_check["segundos_restantes"] <= 900
    print(f"  -> OK: Reserva ACTIVA con {data_check['segundos_restantes']} segundos restantes")

    # --------------------------------------------------------------------------
    # 4. Cancelación / Liberación voluntaria de reserva
    # --------------------------------------------------------------------------
    print("\n[TEST 4] Cancelar reserva anticipada (abandono voluntario de checkout)...")
    reserva_cancel_id = f"RES-CANCEL-{uuid.uuid4().hex[:6].upper()}"
    asyncio.run(crear_reserva_stock(
        reserva_id=reserva_cancel_id,
        cliente_id=cliente_id,
        items=[item_payload],
        ttl_seconds=900
    ))
    
    resp_cancel = carrito_client.post(f"/api/v1/carrito/checkout/reserva/{reserva_cancel_id}/cancelar")
    assert resp_cancel.status_code == 200
    assert resp_cancel.json()["status"] == "RESERVA_CANCELADA"

    resp_after = carrito_client.get(f"/api/v1/carrito/checkout/reserva/{reserva_cancel_id}")
    assert resp_after.status_code == 404
    print("  -> OK: Reserva liberada y locks eliminados de Redis")

    # --------------------------------------------------------------------------
    # 5. Conversión a Orden con confirmación definitiva de reserva (RIO-INV-03)
    # --------------------------------------------------------------------------
    print("\n[TEST 5] Confirmar orden de compra utilizando la reserva activa...")
    orden_payload = {
        "cliente_id": cliente_id,
        "canal": "web",
        "tipo_despacho": "domicilio",
        "direccion_entrega_id": str(uuid.uuid4()),
        "subtotal": 8999.00,
        "total": 8999.00,
        "reserva_id": reserva_id,
        "items": [
            {
                "variante_id": variante_id,
                "sku": "LAP-DELL-XPS15",
                "nombre_producto": "Laptop Dell XPS 15",
                "cantidad": 1,
                "precio_unitario": 8999.00
            }
        ]
    }
    resp_orden = ordenes_client.post("/api/v1/ordenes/", json=orden_payload)
    assert resp_orden.status_code == 201, f"Error al crear orden: {resp_orden.text}"
    orden_data = resp_orden.json()
    assert orden_data["estado"] == "confirmada"
    assert "codigo_orden" in orden_data
    print(f"  -> OK: Orden {orden_data['codigo_orden']} creada y reserva confirmada (RIO-INV-03)")

    # --------------------------------------------------------------------------
    # 6. Rechazo de orden si la reserva expiró (Control concurrente de TTL)
    # --------------------------------------------------------------------------
    print("\n[TEST 6] Rechazo de compra cuando la reserva de stock expiró...")
    reserva_expirada_id = f"RES-EXP-{uuid.uuid4().hex[:6].upper()}"
    # Crear reserva expirada (TTL 0)
    asyncio.run(crear_reserva_stock(
        reserva_id=reserva_expirada_id,
        cliente_id=cliente_id,
        items=[item_payload],
        ttl_seconds=0
    ))

    orden_payload["reserva_id"] = reserva_expirada_id
    resp_exp = ordenes_client.post("/api/v1/ordenes/", json=orden_payload)
    assert resp_exp.status_code == 409, f"Se esperaba 409 Conflict, se obtuvo: {resp_exp.status_code}"
    print("  -> OK: Retorno 409 Conflict verificado ante reserva expirada")

    print("\n" + "=" * 70)
    print("TODAS LAS PRUEBAS DE US-14 (RF-14) PASARON CON ÉXITO")
    print("=" * 70)

if __name__ == "__main__":
    test_reserva_stock_flujo_completo()
