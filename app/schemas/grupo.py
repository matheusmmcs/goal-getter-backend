from uuid import UUID
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.schemas.unidade import UnidadeResponse

class GrupoCreate(BaseModel):
    nome: str
    id_unidade: UUID
    usuarios_participantes: list[UUID] = []
    usuarios_chefes: list[UUID] = []
    inativo: bool = False

class GrupoUpdate(BaseModel):
    nome: Optional[str] = None
    id_unidade: Optional[UUID] = None
    usuarios_participantes: Optional[list[UUID]] = None
    usuarios_chefes: Optional[list[UUID]] = None
    inativo: Optional[bool] = None

class GrupoResponse(BaseModel):
    id: UUID
    nome: str
    id_unidade: UUID
    inativo: bool
    unidade: Optional[UnidadeResponse] = None

    model_config = ConfigDict(from_attributes=True)

class GrupoDetailResponse(GrupoResponse):
    atribuicoes: list = []
