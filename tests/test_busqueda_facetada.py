"""
Pruebas automatizadas para US-06 (RF-06):
Búsqueda por Texto Completo y Filtros Facetados en MaxiConecta.
Ejecutar con: python backend/tests/test_busqueda_facetada.py
"""
import os
import sys

# Asegurar path de importación
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from fastapi.testclient import TestClient
from backend.services.catalogo.app.main import app as catalogo_app

client = TestClient(catalogo_app)


def test_busqueda_facetada_suite():
    print("=" * 70)
    print("INICIANDO SUITE DE PRUEBAS: US-06 / RF-06 BÚSQUEDA FACETADA Y FTS")
    print("=" * 70)

    # --------------------------------------------------------------------------
    # 1. Catálogo inicial y recuento de facetas
    # --------------------------------------------------------------------------
    print("\n[TEST 1] Consulta de búsqueda global sin filtros (Catálogo completo y facetas)...")
    resp = client.get("/api/v1/catalogo/buscar")
    assert resp.status_code == 200, f"Error en búsqueda inicial: {resp.text}"
    data = resp.json()
    assert data["total_coincidencias"] >= 8, f"Se esperaban al menos 8 productos, se obtuvieron {data['total_coincidencias']}"
    assert len(data["facetas"]["categorias"]) >= 4, "Debe incluir facetas de categorías"
    assert len(data["facetas"]["marcas"]) >= 4, "Debe incluir facetas de marcas"
    assert data["facetas"]["precio"]["min"] > 0, "Precio mínimo debe ser mayor a 0"
    assert data["facetas"]["precio"]["max"] >= 8000, "Precio máximo debe reflejar productos de alta gama"
    print(f"  -> OK: {data['total_coincidencias']} productos encontrados.")
    print(f"     Categorías facetadas: {len(data['facetas']['categorias'])}, Marcas facetadas: {len(data['facetas']['marcas'])}")
    print(f"     Rango de precios: Bs. {data['facetas']['precio']['min']} - Bs. {data['facetas']['precio']['max']}")

    # --------------------------------------------------------------------------
    # 2. Búsqueda Full-Text Search insensible a tildes y mayúsculas
    # --------------------------------------------------------------------------
    print("\n[TEST 2] Búsqueda FTS insensible a tildes ('camara' sin tilde vs 'Cámara')...")
    resp_accent = client.get("/api/v1/catalogo/buscar?q=camara")
    assert resp_accent.status_code == 200
    data_accent = resp_accent.json()
    assert data_accent["total_coincidencias"] >= 1, "Debe encontrar 'Cámara Digital Sony'"
    found_title = data_accent["items"][0]["nombre"]
    assert "Cámara" in found_title or "camara" in found_title.lower()
    print(f"  -> OK: Búsqueda 'camara' localizó con éxito: '{found_title}'")

    print("\n[TEST 2.1] Búsqueda FTS insensible a tildes ('mecanico' sin tilde vs 'Mecánico')...")
    resp_mech = client.get("/api/v1/catalogo/buscar?q=mecanico")
    assert resp_mech.status_code == 200
    data_mech = resp_mech.json()
    assert data_mech["total_coincidencias"] >= 1, "Debe encontrar 'Teclado Mecánico'"
    print(f"  -> OK: Búsqueda 'mecanico' localizó: '{data_mech['items'][0]['nombre']}'")

    # --------------------------------------------------------------------------
    # 3. Búsqueda por SKU y marca
    # --------------------------------------------------------------------------
    print("\n[TEST 3] Búsqueda por SKU parcial ('XPS15')...")
    resp_sku = client.get("/api/v1/catalogo/buscar?q=XPS15")
    assert resp_sku.status_code == 200
    data_sku = resp_sku.json()
    assert data_sku["total_coincidencias"] == 1
    assert data_sku["items"][0]["sku"] == "LAP-DELL-XPS15"
    print(f"  -> OK: Localizado producto por SKU: {data_sku['items'][0]['sku']}")

    # --------------------------------------------------------------------------
    # 4. Filtro facetado por marcas múltiples con recuento
    # --------------------------------------------------------------------------
    print("\n[TEST 4] Filtro facetado por marca ('Logitech')...")
    resp_brand = client.get("/api/v1/catalogo/buscar?marcas=Logitech")
    assert resp_brand.status_code == 200
    data_brand = resp_brand.json()
    assert all(item["marca"] == "Logitech" for item in data_brand["items"])
    assert data_brand["total_coincidencias"] >= 2
    # Verificar que en las facetas, la marca Logitech aparece marcada como seleccionada
    logi_facet = next((f for f in data_brand["facetas"]["marcas"] if f["id"].lower() == "logitech"), None)
    assert logi_facet is not None and logi_facet["seleccionado"] is True
    print(f"  -> OK: {data_brand['total_coincidencias']} ítems Logitech filtrados y faceta seleccionada.")

    # --------------------------------------------------------------------------
    # 5. Filtro acumulativo por rango de precios
    # --------------------------------------------------------------------------
    print("\n[TEST 5] Filtro por rango de precio (Bs. 1.000 a Bs. 3.000)...")
    resp_price = client.get("/api/v1/catalogo/buscar?precio_min=1000&precio_max=3000")
    assert resp_price.status_code == 200
    data_price = resp_price.json()
    assert data_price["total_coincidencias"] > 0
    for p in data_price["items"]:
        assert 1000 <= float(p["precio"]) <= 3000, f"Precio {p['precio']} fuera de rango"
    print(f"  -> OK: {data_price['total_coincidencias']} productos dentro del rango 1000 - 3000 BOB.")

    # --------------------------------------------------------------------------
    # 6. Filtros combinados acumulativos (Texto + Marca + Precio)
    # --------------------------------------------------------------------------
    print("\n[TEST 6] Filtro combinado acumulativo: q='Sony' + precio_min=10000...")
    resp_combo = client.get("/api/v1/catalogo/buscar?q=Sony&precio_min=10000")
    assert resp_combo.status_code == 200
    data_combo = resp_combo.json()
    assert data_combo["total_coincidencias"] == 1
    assert "Alpha 7" in data_combo["items"][0]["nombre"]
    print(f"  -> OK: Filtro combinado resolvió exclusivamente: '{data_combo['items'][0]['nombre']}'")

    # --------------------------------------------------------------------------
    # 7. Autocompletado predictivo (Typeahead suggestions)
    # --------------------------------------------------------------------------
    print("\n[TEST 7] Autocompletado predictivo con prefijo 'lap'...")
    resp_sug = client.get("/api/v1/catalogo/sugerencias?q=lap&limite=5")
    assert resp_sug.status_code == 200
    sugerencias = resp_sug.json()
    assert len(sugerencias) >= 2, f"Se esperaban al menos 2 sugerencias de laptops, llegaron {len(sugerencias)}"
    for s in sugerencias:
        assert "lap" in s["nombre"].lower() or "lap" in s["sku"].lower() or "lap" in s["categoria"].lower()
        assert "precio" in s and "imagen_url" in s
    print(f"  -> OK: {len(sugerencias)} sugerencias devueltas:")
    for s in sugerencias:
        print(f"     - [{s['categoria']}] {s['nombre']} ({s['sku']}) - Bs. {s['precio']}")

    # --------------------------------------------------------------------------
    # 8. Ordenamiento dinámico
    # --------------------------------------------------------------------------
    print("\n[TEST 8] Ordenamiento por precio ascendente y descendente...")
    resp_asc = client.get("/api/v1/catalogo/buscar?ordenar_por=precio_asc")
    items_asc = resp_asc.json()["items"]
    precios_asc = [float(i["precio"]) for i in items_asc]
    assert precios_asc == sorted(precios_asc), "Los precios deben estar en orden ascendente"
    print(f"  -> OK: Precio ascendente verificado: {precios_asc[:3]} ...")

    resp_desc = client.get("/api/v1/catalogo/buscar?ordenar_por=precio_desc")
    items_desc = resp_desc.json()["items"]
    precios_desc = [float(i["precio"]) for i in items_desc]
    assert precios_desc == sorted(precios_desc, reverse=True), "Los precios deben estar en orden descendente"
    print(f"  -> OK: Precio descendente verificado: {precios_desc[:3]} ...")

    # --------------------------------------------------------------------------
    # 9. Motor de recomendaciones y venta cruzada (RF-19)
    # --------------------------------------------------------------------------
    print("\n[TEST 9] Consulta de productos recomendados (RF-19)...")
    resp_rec = client.get("/api/v1/catalogo/recomendaciones?limite=4")
    assert resp_rec.status_code == 200
    rec_items = resp_rec.json()
    assert len(rec_items) == 4, f"Se esperaban 4 recomendaciones, se obtuvieron {len(rec_items)}"
    for r in rec_items:
        assert "id" in r and "nombre" in r and "precio" in r and "stock" in r
    print(f"  -> OK: {len(rec_items)} productos recomendados devueltos: {[r['nombre'] for r in rec_items[:2]]}")

    print("\n" + "=" * 70)
    print("¡TODAS LAS PRUEBAS DE US-06 (RF-06) Y US-19 (RF-19) PASARON EXITOSAMENTE (9/9)!")
    print("=" * 70)


if __name__ == "__main__":
    test_busqueda_facetada_suite()
