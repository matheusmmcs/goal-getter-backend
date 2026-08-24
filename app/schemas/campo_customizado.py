import uuid
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from app.models.enums import (
    EntidadeCampoCustomizadoEnum,
    TipoDadoCampoCustomizadoEnum,
)


class OrganizacaoCampoCustomizadoBase(BaseModel):
    entidade: EntidadeCampoCustomizadoEnum = Field(..., description="USUARIO ou UNIDADE")
    nome_campo: str = Field(..., min_length=1, max_length=255, description="Nome de exibição, ex: 'ID no Redmine'")
    chave: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_]+$", description="Slug do campo sem espaços, ex: 'redmine_user_id'")
    tipo_dado: TipoDadoCampoCustomizadoEnum = Field(TipoDadoCampoCustomizadoEnum.TEXTO)
    obrigatorio: bool = Field(False)
    descricao: str | None = Field(None, description="Texto de instrução ou placeholder")


class OrganizacaoCampoCustomizadoCreate(OrganizacaoCampoCustomizadoBase):
    pass


class OrganizacaoCampoCustomizadoUpdate(BaseModel):
    nome_campo: str | None = Field(None, min_length=1, max_length=255)
    tipo_dado: TipoDadoCampoCustomizadoEnum | None = None
    obrigatorio: bool | None = None
    descricao: str | None = None


class OrganizacaoCampoCustomizadoResponse(OrganizacaoCampoCustomizadoBase):
    id: uuid.UUID
    id_organizacao: uuid.UUID
    inativo: bool
    created_at: datetime
    updated_at: datetime | None = None
    ativo: bool

    model_config = ConfigDict(from_attributes=True)


class ValoresCamposCustomizadosUpdate(BaseModel):
    campos_customizados: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
