import pathlib
import sys
from types import SimpleNamespace
from uuid import uuid4

ROOT = pathlib.Path(__file__).resolve().parents[1]
CATALOGO_PATH = str(ROOT / "services" / "catalogo")
sys.path.insert(0, CATALOGO_PATH)
try:
    from backend.services.catalogo.app.routers import _products_response
finally:
    sys.path.remove(CATALOGO_PATH)
    sys.modules.pop("app.schemas", None)
    sys.modules.pop("app", None)


class FakeQuery:
    def __init__(self, client, table):
        self.client = client
        self.table_name = table
        self.filters = {}

    def select(self, *_args):
        return self

    def in_(self, field, values):
        self.filters[field] = {str(value) for value in values}
        return self

    def order(self, *_args, **_kwargs):
        return self

    def execute(self):
        self.client.query_count += 1
        rows = self.client.rows[self.table_name]
        field, accepted = next(iter(self.filters.items()))
        return SimpleNamespace(data=[row for row in rows if str(row[field]) in accepted])


class FakeSupabase:
    def __init__(self, rows):
        self.rows = rows
        self.query_count = 0

    def table(self, name):
        return FakeQuery(self, name)


def test_products_response_loads_relationships_in_constant_queries():
    category_id = uuid4()
    product_rows = [
        {
            "id": uuid4(),
            "sku": f"SKU-{index}",
            "nombre": f"Producto {index}",
            "categoria_id": category_id,
            "estado": "publicado",
        }
        for index in range(40)
    ]
    variant_rows = [
        {
            "id": uuid4(),
            "producto_id": row["id"],
            "sku": f"SKU-{index}-BASE",
            "nombre_variante": "Base",
            "atributos": {},
            "precio": index + 1,
            "precio_costo": 0,
        }
        for index, row in enumerate(product_rows)
    ]
    image_rows = [
        {
            "id": uuid4(),
            "producto_id": row["id"],
            "url": f"https://example.test/{index}.jpg",
            "es_principal": True,
            "orden": 0,
        }
        for index, row in enumerate(product_rows)
    ]
    client = FakeSupabase({
        "categorias": [{"id": category_id, "nombre": "Tecnología", "activo": True}],
        "variantes": variant_rows,
        "imagenes_producto": image_rows,
    })

    products = _products_response(client, product_rows)

    assert len(products) == 40
    assert client.query_count == 3
    assert products[0].precio == 1
    assert len(products[0].variantes) == 1
    assert len(products[0].imagenes_producto) == 1
    assert products[-1].precio == 40
