import uuid

import pytest
from fastapi.testclient import TestClient

from backend.services.clientes.app import routers as clientes_routers
from backend.services.clientes.app.main import app
from backend.shared.security import create_access_token


@pytest.fixture
def direcciones_client(monkeypatch):
    cliente_id = str(uuid.uuid4())
    otro_cliente_id = str(uuid.uuid4())
    monkeypatch.setattr(clientes_routers, "get_supabase_admin_client", lambda: None)
    monkeypatch.setattr(clientes_routers, "_DIRECCIONES_DB", {})
    token = create_access_token({"sub": cliente_id, "user_id": cliente_id, "email": "cliente@test.bo", "role": "cliente"})
    otro_token = create_access_token({"sub": otro_cliente_id, "user_id": otro_cliente_id, "email": "otro@test.bo", "role": "cliente"})
    client = TestClient(app)
    return client, cliente_id, token, otro_token


def test_crud_direcciones_coordenadas_y_predeterminada(direcciones_client):
    client, cliente_id, token, _ = direcciones_client
    headers = {"Authorization": f"Bearer {token}"}
    base = f"/api/v1/clientes/{cliente_id}/direcciones"

    primera = client.post(base, headers=headers, json={
        "direccion": "Av. Arce 123",
        "referencia": "Portón azul, piso 2",
        "ciudad": "La Paz",
        "latitud": -16.5041,
        "longitud": -68.1324,
    })
    assert primera.status_code == 201
    primera_data = primera.json()
    assert primera_data["referencia"] == "Portón azul, piso 2"
    assert primera_data["latitud"] == -16.5041
    assert primera_data["longitud"] == -68.1324
    assert primera_data["es_predeterminada"] is True

    segunda = client.post(base, headers=headers, json={
        "direccion": "Calle 10 #45",
        "ciudad": "La Paz",
        "es_predeterminada": True,
    })
    assert segunda.status_code == 201
    assert segunda.json()["es_predeterminada"] is True

    listado = client.get(base, headers=headers)
    assert listado.status_code == 200
    assert len(listado.json()) == 2
    assert sum(item["es_predeterminada"] for item in listado.json()) == 1
    assert next(item for item in listado.json() if item["id"] == primera_data["id"])["es_predeterminada"] is False

    actualizada = client.patch(f"{base}/{primera_data['id']}", headers=headers, json={
        "referencia": "Recepción de edificio",
        "es_predeterminada": True,
    })
    assert actualizada.status_code == 200
    assert actualizada.json()["referencia"] == "Recepción de edificio"
    assert actualizada.json()["es_predeterminada"] is True

    eliminada = client.delete(f"{base}/{primera_data['id']}", headers=headers)
    assert eliminada.status_code == 204
    restantes = client.get(base, headers=headers).json()
    assert len(restantes) == 1
    assert restantes[0]["es_predeterminada"] is True


def test_direcciones_exigen_propietario_y_coordenadas_pareadas(direcciones_client):
    client, cliente_id, token, otro_token = direcciones_client
    path = f"/api/v1/clientes/{cliente_id}/direcciones"
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"Authorization": f"Bearer {otro_token}"}).status_code == 403

    respuesta = client.post(path, headers={"Authorization": f"Bearer {token}"}, json={
        "direccion": "Calle 1 #2",
        "ciudad": "La Paz",
        "latitud": -16.5,
    })
    assert respuesta.status_code == 422
