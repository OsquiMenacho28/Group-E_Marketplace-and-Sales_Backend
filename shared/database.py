import logging
from typing import Optional
from backend.shared.config import settings

logger = logging.getLogger("maxiconecta.database")

_supabase_client = None
_supabase_admin_client = None

def get_supabase_client():
    """
    Retorna una instancia singleton del cliente Supabase (clave pública/anónima).
    Si las credenciales no están configuradas en dev, emite advertencia.
    """
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    try:
        from supabase import create_client
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

def get_supabase_admin_client():
    """
    Retorna cliente Supabase con privilegios administrativos (service_role_key)
    para operaciones de administración de usuarios y auth.
    """
    global _supabase_admin_client
    if _supabase_admin_client is not None:
        return _supabase_admin_client

    try:
        from supabase import create_client
        key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_KEY
        if settings.SUPABASE_URL and key and key != "anon-key":
            _supabase_admin_client = create_client(settings.SUPABASE_URL, key)
            logger.info("Cliente Supabase Admin inicializado correctamente.")
        else:
            return None
    except Exception as e:
        logger.error(f"Error al inicializar cliente Supabase Admin: {e}")
        return None

    return _supabase_admin_client
