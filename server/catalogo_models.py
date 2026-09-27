"""
Esquema de Base de Datos y Modelo Pydantic v2 para Microservicio de Catálogo
Requerimiento Funcional: RF-01 — Gestión del Ciclo de Vida de Productos
Subtareas:
- KAN-287: [DB] Esquema de tabla productos con restricciones de unicidad de SKU
- KAN-306: [BE] CRUD de productos y validaciones con Pydantic v2
"""

from enum import Enum
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, ConfigDict


# ==============================================================================
# SUBTAREA KAN-287: DDL / SQL para PostgreSQL (Supabase)
# Restricción UNIQUE en columna 'sku' e índices de búsqueda
# ==============================================================================
SQL_CATALOGO_DDL = """
-- 1. Tipo Enum para el ciclo de vida del producto
DO $$ BEGIN
    CREATE TYPE estado_producto_enum AS ENUM ('borrador', 'publicado', 'descontinuado', 'inactivo');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- 2. Asegurar que la tabla productos tenga restricción UNIQUE en SKU
ALTER TABLE productos 
    DROP CONSTRAINT IF EXISTS uq_productos_sku;

ALTER TABLE productos 
    ADD CONSTRAINT uq_productos_sku UNIQUE (sku);

-- 3. Índices para acelerar búsquedas y paginación en panel Admin y Marketplace
CREATE INDEX IF NOT EXISTS idx_productos_sku ON productos(sku);
CREATE INDEX IF NOT EXISTS idx_productos_estado ON productos(estado);
CREATE INDEX IF NOT EXISTS idx_productos_categoria ON productos(categoria_id);
"""


# ==============================================================================
# SUBTAREA KAN-306: Modelos Pydantic v2 con validaciones estrictas
# ==============================================================================

class EstadoProducto(str, Enum):
    BORRADOR = "borrador"
    PUBLICADO = "publicado"
    DESCONTINUADO = "descontinuado"
    INACTIVO = "inactivo"


class ProductoBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)

    sku: str = Field(
        ..., 
        min_length=3, 
        max_length=50, 
        description="Código SKU único del producto. Se transforma a mayúsculas automáticamente.",
        examples=["LAP-DELL-XPS15", "MOU-LOG-MX3S"]
    )
    nombre: str = Field(
        ..., 
        min_length=2, 
        max_length=255, 
        description="Nombre comercial descriptivo del producto"
    )
    descripcion: Optional[str] = Field(
        default="", 
        max_length=2000, 
        description="Detalle técnico y características"
    )
    marca: Optional[str] = Field(
        default="", 
        max_length=100, 
        description="Marca o fabricante"
    )
    categoria_id: Optional[UUID] = Field(
        default=None, 
        description="ID UUID de la categoría asociada"
    )
    estado: EstadoProducto = Field(
        default=EstadoProducto.PUBLICADO, 
        description="Ciclo de vida del producto"
    )

    @field_validator("sku")
    @classmethod
    def validar_sku(cls, v: str) -> str:
        v = v.strip().upper()
        if not v.isalnum() and not any(c in v for c in "-_"):
            raise ValueError("El SKU solo puede contener caracteres alfanuméricos, guiones (-) y guiones bajos (_)")
        return v


class ProductoCreate(ProductoBase):
    """Payload para POST /api/productos"""
    pass


class ProductoUpdate(BaseModel):
    """Payload para PUT/PATCH /api/productos/:id"""
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)

    sku: Optional[str] = Field(None, min_length=3, max_length=50)
    nombre: Optional[str] = Field(None, min_length=2, max_length=255)
    descripcion: Optional[str] = Field(None, max_length=2000)
    marca: Optional[str] = Field(None, max_length=100)
    categoria_id: Optional[UUID] = None
    estado: Optional[EstadoProducto] = None

    @field_validator("sku")
    @classmethod
    def validar_sku(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip().upper()
            if not v.isalnum() and not any(c in v for c in "-_"):
                raise ValueError("El SKU solo puede contener caracteres alfanuméricos, guiones (-) y guiones bajos (_)")
        return v


class ProductoEstadoUpdate(BaseModel):
    """Payload rápido para PATCH /api/productos/:id/estado"""
    estado: EstadoProducto


class CategoriaSimple(BaseModel):
    id: UUID
    nombre: str


class ImagenProductoSimple(BaseModel):
    id: UUID
    url: str
    es_principal: bool
    orden: int


class ProductoResponse(ProductoBase):
    """Respuesta serializada de producto"""
    id: UUID
    created_at: Optional[datetime] = None
    categorias: Optional[CategoriaSimple] = None
    imagenes_producto: Optional[List[ImagenProductoSimple]] = []


class PaginatedProductosResponse(BaseModel):
    """Respuesta paginada para KAN-291"""
    total: int
    page: int
    page_size: int
    total_pages: int
    productos: List[ProductoResponse]
