from uuid import UUID
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.schemas.unidade import UnidadeResponse

from datetime import datetime

class UsuarioBase(BaseModel):
    usuario: str
    nome: str
    nickname: Optional[str] = None
    email: Optional[str] = None
    cpf: Optional[str] = None

class UsuarioCreate(UsuarioBase):
    senha: str
    is_admin: bool = False
    is_autorizado: bool = False

class UsuarioRegister(BaseModel):
    usuario: str
    nome: str
    senha: str
    email: str
    nickname: Optional[str] = None
    cpf: Optional[str] = None

class UsuarioUpdate(BaseModel):
    usuario: Optional[str] = None
    nome: Optional[str] = None
    nickname: Optional[str] = None
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
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    data_autorizacao: Optional[datetime] = None
    data_inativacao: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class UsuarioDetailResponse(UsuarioResponse):
    perfis: list = []
    atribuicoes: list = []
