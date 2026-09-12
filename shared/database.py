import logging
from typing import Optional
from backend.shared.config import settings

logger = logging.getLogger("maxiconecta.database")

_supabase_client = None

def get_supabase_client():
    """
    Retorna una instancia singleton del cliente Supabase.
    Si las credenciales no están configuradas en dev, emite advertencia.
    """
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    try:
        from supabase import create_client, Client
        if settings.SUPABASE_URL and settings.SUPABASE_KEY and settings.SUPABASE_KEY != "anon-key":
            _supabase_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
            logger.info("Cliente Supabase inicializado correctamente.")
        else:
            logger.warning("Credenciales de Supabase en modo placeholder/desarrollo local.")
            return None
    except Exception as e:
        logger.error(f"Error al inicializar cliente Supabase: {e}")
        return None

    return _supabase_client
