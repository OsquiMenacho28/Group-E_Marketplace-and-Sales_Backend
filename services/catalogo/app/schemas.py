from typing import List, Optional, Dict, Any
from uuid import UUID
from decimal import Decimal
from pydantic import BaseModel, Field

class CategoriaBase(BaseModel):
    nombre: str
    descripcion: Optional[str] = None
    padre_id: Optional[UUID] = None
    atributos_dinamicos: List[str] = []

class CategoriaResponse(CategoriaBase):
    id: UUID
    activo: bool = True

class VarianteBase(BaseModel):
    sku: str
    nombre_variante: str
    atributos: Dict[str, Any] = {}
    precio: Decimal = Field(..., ge=0)
    precio_costo: Decimal = Field(default=Decimal("0.0"), ge=0)
    codigo_barras: Optional[str] = None

class VarianteResponse(VarianteBase):
    id: UUID
    producto_id: UUID

class ImagenProductoCreate(BaseModel):
    data_url: str = Field(..., min_length=32, max_length=7_000_000)
    nombre: Optional[str] = Field(default=None, max_length=160)

class ImagenProductoResponse(BaseModel):
    id: UUID
    url: str
    nombre: Optional[str] = None
    es_principal: bool = False
    orden: int = 0

class ProductoCreate(BaseModel):
    sku: str
    nombre: str
    descripcion: Optional[str] = None
    marca: Optional[str] = None
    categoria_id: UUID
    precio: Decimal = Field(..., ge=0)
    variantes: List[VarianteBase] = []
    imagenes: List[ImagenProductoCreate] = Field(default_factory=list, max_length=5)

class ProductoResponse(BaseModel):
    id: UUID
    sku: str
    nombre: str
    descripcion: Optional[str] = None
    marca: Optional[str] = None
    categoria_id: UUID
    estado: str = "publicado"
    variantes: List[VarianteResponse] = []
    precio: Decimal = Field(default=Decimal("0"), ge=0)
    categorias: Optional[CategoriaResponse] = None
    imagenes_producto: List[ImagenProductoResponse] = []
