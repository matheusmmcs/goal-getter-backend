from uuid import UUID
from typing import Optional
from pydantic import BaseModel, ConfigDict

class UnidadeCreate(BaseModel):
    nome: str
    nome_ascii: Optional[str] = None
    sigla: Optional[str] = None
    codigo: Optional[int] = None
    id_unidade_pai: Optional[UUID] = None
    inativo: bool = False

class UnidadeUpdate(BaseModel):
    nome: Optional[str] = None
    nome_ascii: Optional[str] = None
    sigla: Optional[str] = None
    codigo: Optional[int] = None
    id_unidade_pai: Optional[UUID] = None
    inativo: Optional[bool] = None

class UnidadeResponse(BaseModel):
    id: UUID
    nome: str
    nome_ascii: Optional[str] = None
    sigla: Optional[str] = None
    codigo: Optional[int] = None
    id_unidade_pai: Optional[UUID] = None
    inativo: bool

    model_config = ConfigDict(from_attributes=True)
