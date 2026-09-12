"""
Script de verificación de conexión a Supabase para MaxiConecta.
Ejecutar con: python backend/test_supabase.py
"""
import sys
import os

# Asegurar que el path incluya la raíz del proyecto
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.shared.config import settings
from backend.shared.database import get_supabase_client

def main():
    print("=" * 60)
    print("[INFO] VERIFICACION DE CONEXION A SUPABASE - MAXICONECTA")
    print("=" * 60)
    
    print(f"[*] SUPABASE_URL: {settings.SUPABASE_URL}")
    print(f"[*] SUPABASE_KEY: {'Configurada' if settings.SUPABASE_KEY and settings.SUPABASE_KEY != 'anon-key' else '[!] NO CONFIGURADA (Valor por defecto)'}")
    
    if not settings.SUPABASE_URL or "tu-proyecto" in settings.SUPABASE_URL:
        print("\n[ERROR] Debes configurar SUPABASE_URL en tu archivo .env")
        return

    if not settings.SUPABASE_KEY or settings.SUPABASE_KEY == "anon-key":
        print("\n[ERROR] Debes configurar SUPABASE_KEY con tu clave anon publica en .env\n")
        return

    print("\nConectando con Supabase...")
    client = get_supabase_client()
    if client:
        try:
            response = client.table("categorias").select("id, nombre").limit(5).execute()
            print("[OK] Conexion exitosa a Supabase via SDK!")
            print(f"Categorias encontradas en la base de datos: {len(response.data)}")
            for cat in response.data:
                print(f"   - {cat.get('nombre')} (ID: {cat.get('id')})")
        except Exception as e:
            print(f"[ALERTA] Conexion establecida pero fallo la consulta a 'categorias':\n   {e}")
            print("Asegurate de haber ejecutado el script 'backend/db/schema.sql' en el SQL Editor de Supabase.")
    else:
        # Fallback usando urllib estándar (no requiere pip install)
        import urllib.request
        import json
        
        endpoint = f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/categorias?select=id,nombre&limit=5"
        headers = {
            "apikey": settings.SUPABASE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        req = urllib.request.Request(endpoint, headers=headers)
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode())
                print("[OK] Conexion REST exitosa a Supabase (PostgREST API)!")
                print(f"Categorias encontradas en la base de datos: {len(data)}")
                for cat in data:
                    print(f"   - {cat.get('nombre')} (ID: {cat.get('id')})")
        except urllib.error.HTTPError as e:
            print(f"[ALERTA] Respuesta HTTP {e.code} desde Supabase:")
            err_body = e.read().decode()
            print(f"   {err_body}")
            if e.code == 404 or "relation" in err_body or "does not exist" in err_body or "PGRST205" in err_body:
                print("\n--> [CONEXION EXITOSA]: Las credenciales son validas y conectan con Supabase.")
                print("    Sin embargo, la tabla 'categorias' aun no existe en el proyecto.")
                print("    PASO PENDIENTE: Abre Supabase > SQL Editor, pega el contenido de")
                print("    'backend/db/schema.sql' y dale a 'RUN' para crear las 22 tablas.")
        except Exception as e:
            print(f"[ERROR] No se pudo conectar a Supabase:\n   {e}")

    print("=" * 60)

if __name__ == "__main__":
    main()
