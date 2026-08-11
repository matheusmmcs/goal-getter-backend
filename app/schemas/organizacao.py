from uuid import UUID
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from app.models.enums import PapelOrganizacaoEnum


class UsuarioVinculoItem(BaseModel):
    id_usuario: UUID
    papel_organizacao: PapelOrganizacaoEnum = PapelOrganizacaoEnum.MEMBRO


class OrganizacaoBase(BaseModel):
    nome: str
    sigla: Optional[str] = None
    descricao: Optional[str] = None


class OrganizacaoCreate(OrganizacaoBase):
    usuarios_vinculos: Optional[List[UsuarioVinculoItem]] = []


class OrganizacaoUpdate(BaseModel):
    nome: Optional[str] = None
    sigla: Optional[str] = None
    descricao: Optional[str] = None
    inativo: Optional[bool] = None


class UsuarioOrganizacaoVinculoResponse(BaseModel):
    id: UUID
    id_usuario: UUID
    id_organizacao: UUID
    papel_organizacao: PapelOrganizacaoEnum
    inativo: bool
    created_at: datetime
    usuario_nome: Optional[str] = None
    usuario_login: Optional[str] = None
    usuario_email: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class OrganizacaoResponse(OrganizacaoBase):
    id: UUID
    inativo: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class OrganizacaoDetailResponse(OrganizacaoResponse):
    usuarios_vinculos: List[UsuarioOrganizacaoVinculoResponse] = []
    unidades_count: int = 0
    grupos_count: int = 0


class VinculoUpdateSchema(BaseModel):
    papel_organizacao: PapelOrganizacaoEnum
    inativo: Optional[bool] = False
