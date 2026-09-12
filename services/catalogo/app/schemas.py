from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
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

class ProductoCreate(BaseModel):
    sku: str
    nombre: str
    descripcion: Optional[str] = None
    marca: Optional[str] = None
    categoria_id: UUID
    variantes: List[VarianteBase] = []

class ProductoResponse(BaseModel):
    id: UUID
    sku: str
    nombre: str
    descripcion: Optional[str] = None
    marca: Optional[str] = None
    categoria_id: UUID
    estado: str = "publicado"
    variantes: List[VarianteResponse] = []
