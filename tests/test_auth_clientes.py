"""
Pruebas automatizadas para US-22 / US-49: Autenticación Multi-Rol y Clientes en MaxiConecta.
Ejecutar con: python backend/tests/test_auth_clientes.py
"""
import sys
import os

# Asegurar que el path incluya la raíz del proyecto
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from fastapi.testclient import TestClient
from backend.services.clientes.app.main import app

client = TestClient(app)

def test_auth_flow():
    print("=" * 60)
    print("INICIANDO SUITE DE PRUEBAS: US-22 / US-49 AUTENTICACIÓN MULTI-ROL")
    print("=" * 60)

    # 1. Login con cuenta semilla de Administrador
    print("\n[TEST 1] Login de Administrador (admin@maxiconecta.bo)...")
    resp_admin = client.post("/api/v1/clientes/auth/login", json={
        "email": "admin@maxiconecta.bo",
        "password": "Admin123!"
    })
    assert resp_admin.status_code == 200, f"Error en login admin: {resp_admin.text}"
    admin_data = resp_admin.json()
    assert admin_data["user"]["role"] == "administrador"
    assert "access_token" in admin_data
    print("  -> OK: Administrador autenticado con rol 'administrador'")

    # 2. Login con cuenta semilla de Cajero
    print("\n[TEST 2] Login de Cajero POS (cajero@maxiconecta.bo)...")
    resp_cajero = client.post("/api/v1/clientes/auth/login", json={
        "email": "cajero@maxiconecta.bo",
        "password": "Cajero123!"
    })
    assert resp_cajero.status_code == 200, f"Error en login cajero: {resp_cajero.text}"
    cajero_data = resp_cajero.json()
    assert cajero_data["user"]["role"] == "cajero"
    assert cajero_data["user"]["sucursal_id"] == "sucursal-central-001"
    print("  -> OK: Cajero autenticado con rol 'cajero' y sucursal asignada")

    # 3. Login con contraseña incorrecta (Debe fallar con 401)
    print("\n[TEST 3] Rechazo ante credenciales erróneas...")
    resp_fail = client.post("/api/v1/clientes/auth/login", json={
        "email": "admin@maxiconecta.bo",
        "password": "PasswordEquivocado999"
    })
    assert resp_fail.status_code == 401
    print("  -> OK: Retorno 401 Unauthorized verificado")

    # 4. Registro de un nuevo cliente retail (RF-22)
    nuevo_email = f"maria.lopez.{os.urandom(4).hex()}@example.com"
    print(f"\n[TEST 4] Registro de nuevo cliente ({nuevo_email})...")
    resp_reg = client.post("/api/v1/clientes/auth/registro", json={
        "nombre_completo": "María López Fernández",
        "email": nuevo_email,
        "password": "PasswordSeguro123!",
        "telefono": "+591 78901234",
        "tipo_cliente": "retail"
    })
    assert resp_reg.status_code == 201, f"Error en registro: {resp_reg.text}"
    reg_data = resp_reg.json()
    assert reg_data["user"]["role"] == "cliente"
    assert reg_data["user"]["puntos_saldo"] == 50, f"Puntos esperados 50, obtenidos {reg_data['user']['puntos_saldo']}"
    token_cliente = reg_data["access_token"]
    refresh_token = reg_data["refresh_token"]
    print("  -> OK: Cliente registrado con éxito, token emitido y 50 puntos de bienvenida acreditados")

    # 5. Rechazo de correo duplicado
    print("\n[TEST 5] Rechazo ante correo duplicado...")
    resp_dup = client.post("/api/v1/clientes/auth/registro", json={
        "nombre_completo": "María Duplicada",
        "email": nuevo_email,
        "password": "PasswordSeguro123!"
    })
    assert resp_dup.status_code == 400
    print("  -> OK: Correo duplicado rechazado con HTTP 400")

    # 6. Consulta de perfil protegido /me con token Bearer
    print("\n[TEST 6] Consulta a endpoint protegido /me con Bearer token...")
    resp_me = client.get(
        "/api/v1/clientes/auth/me",
        headers={"Authorization": f"Bearer {token_cliente}"}
    )
    assert resp_me.status_code == 200, f"Error en /me: {resp_me.text}"
    me_data = resp_me.json()
    assert me_data["email"] == nuevo_email
    assert me_data["puntos_saldo"] == 50
    assert me_data["role"] == "cliente"
    print(f"  -> OK: Identidad verificada para {me_data['nombre_completo']} ({me_data['puntos_saldo']} pts)")

    # 7. Consulta a /me sin token (Debe retornar 401)
    print("\n[TEST 7] Rechazo en /me sin token de autorización...")
    resp_no_token = client.get("/api/v1/clientes/auth/me")
    assert resp_no_token.status_code == 401
    print("  -> OK: Acceso denegado sin token (HTTP 401)")

    # 8. Renovación de token de sesión con refresh_token
    print("\n[TEST 8] Renovación de token de acceso con refresh_token...")
    resp_refresh = client.post("/api/v1/clientes/auth/refresh", json={
        "refresh_token": refresh_token
    })
    assert resp_refresh.status_code == 200, f"Error en refresh: {resp_refresh.text}"
    refresh_data = resp_refresh.json()
    assert "access_token" in refresh_data
    print("  -> OK: Nuevo access token emitido exitosamente")

    print("\n" + "=" * 60)
    print("TODAS LAS PRUEBAS DE AUTENTICACIÓN (8/8) PASARON SATISFACTORIAMENTE!")
    print("=" * 60)

if __name__ == "__main__":
    test_auth_flow()
