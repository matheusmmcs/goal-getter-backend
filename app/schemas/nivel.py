from uuid import UUID
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.models.enums import TipoNivelEnum

class NivelCreate(BaseModel):
    nome: str
    tipo: TipoNivelEnum
    valor: int
    inativo: bool = False

class NivelUpdate(BaseModel):
    nome: Optional[str] = None
    tipo: Optional[TipoNivelEnum] = None
    valor: Optional[int] = None
    inativo: Optional[bool] = None

class NivelResponse(BaseModel):
    id: UUID
    nome: str
    tipo: TipoNivelEnum
    valor: int
    inativo: bool

    model_config = ConfigDict(from_attributes=True)
