import os
from typing import Optional
from pydantic import BaseModel

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

class Settings(BaseModel):
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")

    # Supabase / DB
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "https://tu-proyecto.supabase.co")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "anon-key")
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = os.getenv("SUPABASE_SERVICE_ROLE_KEY", None)
    SUPABASE_PUBLISHABLE_KEY: Optional[str] = os.getenv("SUPABASE_PUBLISHABLE_KEY", None)
    SUPABASE_SECRET_KEY: Optional[str] = os.getenv("SUPABASE_SECRET_KEY", None)
    SUPABASE_JWKS_URL: Optional[str] = os.getenv("SUPABASE_JWKS_URL", None)
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/maxiconecta")

    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # JWT
    JWT_SECRET: str = os.getenv("JWT_SECRET", "super-secret-dev-key")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")

    # URLs Microservicios
    MS_CATALOGO_URL: str = os.getenv("MS_CATALOGO_URL", "http://localhost:8001")
    MS_POS_URL: str = os.getenv("MS_POS_URL", "http://localhost:8002")
    MS_CARRITO_URL: str = os.getenv("MS_CARRITO_URL", "http://localhost:8003")
    MS_CLIENTES_URL: str = os.getenv("MS_CLIENTES_URL", "http://localhost:8004")
    MS_ORDENES_URL: str = os.getenv("MS_ORDENES_URL", "http://localhost:8005")
    MS_REPORTES_URL: str = os.getenv("MS_REPORTES_URL", "http://localhost:8006")

    # ERP Externos (RIO)
    ERP_INVENTARIOS_URL: str = os.getenv("ERP_INVENTARIOS_URL", "http://localhost:9001")
    ERP_PAGOS_URL: str = os.getenv("ERP_PAGOS_URL", "http://localhost:9002")
    ERP_CONTABILIDAD_URL: str = os.getenv("ERP_CONTABILIDAD_URL", "http://localhost:9003")
    ERP_CRM_URL: str = os.getenv("ERP_CRM_URL", "http://localhost:9004")
    ERP_ENTREGAS_URL: str = os.getenv("ERP_ENTREGAS_URL", "http://localhost:9005")
    ERP_PRODUCCION_URL: str = os.getenv("ERP_PRODUCCION_URL", "http://localhost:9006")
    ERP_TIMEOUT_SECONDS: float = float(os.getenv("ERP_TIMEOUT_SECONDS", "5.0"))

settings = Settings()
