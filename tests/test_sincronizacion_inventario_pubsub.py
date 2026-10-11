"""
Pruebas de Integración para KAN-56 / KAN-278 (RF-40 · RIO-INV-03 / RIO-INV-04):
Sincronización de Descuentos y Reintegros de Inventario vía Google Cloud Pub/Sub.

Ejecutar con: python Group-E_Marketplace-and-Sales_Backend-main/tests/test_sincronizacion_inventario_pubsub.py
"""
import sys
import os
import uuid
import asyncio

# Asegurar path de importación
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.shared.pubsub_client import pubsub_client, EVENTOS_PUBSUB_LOG
from backend.shared.erp_clients.inventarios import inventarios_client
from backend.shared import stock_ledger


def test_contrato_cloudevents_estructura():
    print("\n[TEST 1] Verificación del esquema CloudEvents v1.0 y atributos Pub/Sub...")
    res = asyncio.run(pubsub_client.publicar_mensaje_test(
        responsable="Kevin Sancalli",
        detalle="Verificacion de estructura de envelope CloudEvents v1.0"
    ))
    assert res is not None, "La respuesta de publicación no debe ser nula"
    assert "event_id" in res, "Debe contener event_id único"
    assert res["event_type"] == "prueba_docente"
    assert "timestamp" in res
    assert res.get("status") in ["PUBLICADO", "FALLBACK_OFFLINE"]
    assert res.get("attributes", {}).get("grupo") == "Grupo-E"
    assert res.get("attributes", {}).get("modulo") == "Marketplace-and-Sales"
    print(f"  -> OK: Evento generado con message_id={res.get('message_id')} y topic={res.get('topic')}")


def test_descuento_stock_publicacion():
    print("\n[TEST 2] Verificación de publicación de evento 'stock.descuento' (RIO-INV-03)...")
    orden_id = f"ORD-TEST-{uuid.uuid4().hex[:6].upper()}"
    items = [
        {"sku": "MED-PAR-500", "cantidad": 3, "nombre": "Paracetamol 500mg"},
        {"sku": "MED-AMO-250", "cantidad": 1, "nombre": "Amoxicilina 250mg"}
    ]

    res = asyncio.run(pubsub_client.publicar_descuento_stock(
        orden_id=orden_id,
        items=items,
        origen="marketplace",
        sucursal_id="SUC-LP-CENTRAL",
        reserva_id="RES-TEST-12345"
    ))

    assert res["event_type"] == "stock.descuento"
    assert res["payload"]["orden_id"] == orden_id
    assert res["payload"]["tipo_movimiento"] == "DESCUENTO_DEFINITIVO"
    assert len(res["payload"]["items"]) == 2
    assert res["payload"]["items"][0]["sku"] == "MED-PAR-500"
    assert res["payload"]["items"][0]["cantidad"] == 3
    print(f"  -> OK: Descuento definitivo publicado para {orden_id} con {len(items)} ítems")


def test_reintegro_stock_publicacion():
    print("\n[TEST 3] Verificación de publicación de evento 'stock.reintegro' (RIO-INV-04)...")
    orden_id = f"ORD-TEST-{uuid.uuid4().hex[:6].upper()}"
    items = [
        {"sku": "MED-PAR-500", "cantidad": 3, "nombre": "Paracetamol 500mg"}
    ]

    res = asyncio.run(pubsub_client.publicar_reintegro_stock(
        orden_id=orden_id,
        items=items,
        motivo="cancelacion_cliente",
        origen="marketplace"
    ))

    assert res["event_type"] == "stock.reintegro"
    assert res["payload"]["orden_id"] == orden_id
    assert res["payload"]["tipo_movimiento"] == "REINTEGRO_DEVOLUCION"
    assert res["payload"]["motivo"] == "cancelacion_cliente"
    print(f"  -> OK: Reintegro de stock por cancelación emitido exitosamente")


def test_integracion_erp_inventarios_client():
    print("\n[TEST 4] Integración de inventarios_client con triggers automáticos de Pub/Sub...")
    orden_id = f"ORD-E2E-{uuid.uuid4().hex[:6].upper()}"
    items = [{"sku": "SKU-AUTO-01", "cantidad": 2, "nombre": "Producto Auto"}]

    # Simular stock inicial
    asyncio.run(stock_ledger.register_base_stock("SKU-AUTO-01", 10))

    # 1. Descuento directo POS / Marketplace
    res_desc = asyncio.run(inventarios_client.descuento_directo(items, orden_id=orden_id))
    assert res_desc.get("status") in ["DESCONTADO", "CONFIRMADA"], "El descuento debe ser exitoso"

    # Verificar que el stock local disminuyó de 10 a 8
    stock_actual = asyncio.run(stock_ledger.available_stock("SKU-AUTO-01"))
    assert stock_actual == 8, f"Se esperaban 8 unidades, se obtuvo {stock_actual}"
    print(f"  -> OK: Stock disminuido a {stock_actual} unidades y evento emitido")

    # 2. Reintegro por devolución
    res_reint = asyncio.run(inventarios_client.reingreso_por_devolucion(orden_id, items, motivo="devolucion_garantia"))
    assert res_reint.get("status") == "REINGRESADO"

    # Verificar que el stock local se restableció a 10
    stock_restablecido = asyncio.run(stock_ledger.available_stock("SKU-AUTO-01"))
    assert stock_restablecido == 10, f"Se esperaban 10 unidades, se obtuvo {stock_restablecido}"
    print(f"  -> OK: Stock reintegrado a {stock_restablecido} unidades tras devolución")


def test_auditoria_eventos_registrados():
    print("\n[TEST 5] Verificación de trazabilidad y cola de auditoría de eventos...")
    assert len(EVENTOS_PUBSUB_LOG) >= 4, "Debe haber registros de auditoría de los eventos emitidos"
    tipos_emitidos = {e["event_type"] for e in EVENTOS_PUBSUB_LOG}
    assert "stock.descuento" in tipos_emitidos
    assert "stock.reintegro" in tipos_emitidos
    print(f"  -> OK: {len(EVENTOS_PUBSUB_LOG)} eventos auditados con trazabilidad completa: {tipos_emitidos}")


if __name__ == "__main__":
    print("=" * 75)
    print("SUITE KAN-278: PRUEBAS DE INTEGRACIÓN SINCRONIZACIÓN INVENTARIOS (PUBSUB)")
    print("=" * 75)
    test_contrato_cloudevents_estructura()
    test_descuento_stock_publicacion()
    test_reintegro_stock_publicacion()
    test_integracion_erp_inventarios_client()
    test_auditoria_eventos_registrados()
    print("\n" + "=" * 75)
    print("¡TODAS LAS PRUEBAS DE INTEGRACIÓN PASARON EXITOSAMENTE (5/5)!")
    print("=" * 75)
