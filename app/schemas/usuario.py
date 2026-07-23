from uuid import UUID
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.schemas.unidade import UnidadeResponse

class UsuarioBase(BaseModel):
    usuario: str
    nome: str
    email: Optional[str] = None
    cpf: Optional[str] = None

class UsuarioCreate(UsuarioBase):
    senha: str
    is_admin: bool = False
    is_autorizado: bool = False

class UsuarioUpdate(BaseModel):
    usuario: Optional[str] = None
    nome: Optional[str] = None
    email: Optional[str] = None
    cpf: Optional[str] = None
    senha: Optional[str] = None
    is_admin: Optional[bool] = None
    is_autorizado: Optional[bool] = None
    inativo: Optional[bool] = None

class UsuarioResponse(UsuarioBase):
    id: UUID
    is_admin: bool
    is_autorizado: bool
    inativo: bool

    model_config = ConfigDict(from_attributes=True)

class UsuarioDetailResponse(UsuarioResponse):
    perfis: list = []
    atribuicoes: list = []
