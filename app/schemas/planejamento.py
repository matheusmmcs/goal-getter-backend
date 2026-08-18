from datetime import datetime, date
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import MetaStatusEnum, OrigemPlanejamentoEnum, OrigemEntregaEnum, EntregaStatusEnum


# ==========================================
# METAS SCHEMAS
# ==========================================

class MetaBase(BaseModel):
    titulo: str = Field(..., min_length=1, max_length=255)
    descricao: str | None = None
    codigo: str | None = None
    valor_meta_inicial: float = Field(0.0, ge=0.0)
    valor_meta_pretendida: float = Field(0.0, ge=0.0)
    valor_meta_atual: float = Field(0.0, ge=0.0)
    data_inicio: date | None = None
    data_fim: date | None = None
    status: MetaStatusEnum = MetaStatusEnum.PLANEJADA
    tipo_origem: OrigemPlanejamentoEnum = OrigemPlanejamentoEnum.INTERNA
    id_unidade: UUID | None = None


class MetaCreate(MetaBase):
    pass


class MetaUpdate(BaseModel):
    titulo: str | None = Field(None, min_length=1, max_length=255)
    descricao: str | None = None
    codigo: str | None = None
    valor_meta_inicial: float | None = Field(None, ge=0.0)
    valor_meta_pretendida: float | None = Field(None, ge=0.0)
    valor_meta_atual: float | None = Field(None, ge=0.0)
    data_inicio: date | None = None
    data_fim: date | None = None
    status: MetaStatusEnum | None = None
    tipo_origem: OrigemPlanejamentoEnum | None = None
    id_unidade: UUID | None = None


class MetaResponse(BaseModel):
    id: UUID
    id_organizacao: UUID
    id_unidade: UUID | None = None
    unidade_nome: str | None = None
    titulo: str
    descricao: str | None = None
    codigo: str | None = None
    valor_meta_inicial: float
    valor_meta_pretendida: float
    valor_meta_atual: float
    progresso_percentual: float = 0.0
    total_entregas: int = 0
    total_entregas_concluidas: int = 0
    data_inicio: date | None = None
    data_fim: date | None = None
    status: MetaStatusEnum
    tipo_origem: OrigemPlanejamentoEnum
    inativo: bool
    created_at: datetime
    updated_at: datetime | None = None
    ativo: bool

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# ENTREGAS SCHEMAS
# ==========================================

class EntregaBase(BaseModel):
    id_meta: UUID | None = None
    id_unidade: UUID | None = None
    id_usuario_responsavel: UUID | None = None
    titulo: str = Field(..., min_length=1, max_length=255)
    descricao: str | None = None
    tipo_origem: OrigemEntregaEnum = OrigemEntregaEnum.INTERNA
    data_inicio: date | None = None
    data_fim: date | None = None
    data_conclusao: date | None = None
    status: EntregaStatusEnum = EntregaStatusEnum.NAO_INICIADA
    progresso_percentual: int = Field(0, ge=0, le=100)
    external_id: str | None = None
    external_data: dict | None = None


class EntregaCreate(EntregaBase):
    pass


class EntregaUpdate(BaseModel):
    id_meta: UUID | None = None
    id_unidade: UUID | None = None
    id_usuario_responsavel: UUID | None = None
    titulo: str | None = Field(None, min_length=1, max_length=255)
    descricao: str | None = None
    tipo_origem: OrigemEntregaEnum | None = None
    data_inicio: date | None = None
    data_fim: date | None = None
    data_conclusao: date | None = None
    status: EntregaStatusEnum | None = None
    progresso_percentual: int | None = Field(None, ge=0, le=100)
    external_id: str | None = None
    external_data: dict | None = None


class EntregaResponse(BaseModel):
    id: UUID
    id_organizacao: UUID
    id_meta: UUID | None = None
    meta_titulo: str | None = None
    id_unidade: UUID | None = None
    unidade_nome: str | None = None
    id_usuario_responsavel: UUID | None = None
    usuario_responsavel_nome: str | None = None
    id_integracao_config: UUID | None = None
    external_id: str | None = None
    titulo: str
    descricao: str | None = None
    tipo_origem: OrigemEntregaEnum
    data_inicio: date | None = None
    data_fim: date | None = None
    data_conclusao: date | None = None
    status: EntregaStatusEnum
    progresso_percentual: int
    external_data: dict | None = None
    inativo: bool
    created_at: datetime
    updated_at: datetime | None = None
    ativo: bool

    model_config = ConfigDict(from_attributes=True)


class EntregaResumoResponse(BaseModel):
    id: UUID
    titulo: str
    tipo_origem: OrigemEntregaEnum
    status: EntregaStatusEnum
    progresso_percentual: int
    data_fim: date | None = None
    id_meta: UUID | None = None
    meta_titulo: str | None = None
    id_unidade: UUID | None = None
    unidade_nome: str | None = None

    model_config = ConfigDict(from_attributes=True)

