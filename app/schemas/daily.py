from uuid import UUID
from typing import Optional
from datetime import date
from pydantic import BaseModel, ConfigDict
from app.models.enums import TipoDiarioItemAnotacaoEnum
from app.schemas.grupo import GrupoResponse
from app.schemas.atribuicao import AtribuicaoResponse

class DiarioConfigResponse(BaseModel):
    id: UUID
    periodo_addnota_inicio: Optional[str] = None
    periodo_addnota_fim: Optional[str] = None
    is_retroativo: bool
    is_permite_atrasado: bool
    is_publico_para_grupo: bool
    canal_chatmessage: Optional[str] = None
    inativo: bool
    grupo: Optional[GrupoResponse] = None

    model_config = ConfigDict(from_attributes=True)

class DiarioConfigCreate(BaseModel):
    periodo_addnota_inicio: Optional[str] = "08:00"
    periodo_addnota_fim: Optional[str] = "18:00"
    is_retroativo: bool = True
    is_permite_atrasado: bool = True
    is_publico_para_grupo: bool = True
    canal_chatmessage: Optional[str] = None

class DiarioConfigUpdate(BaseModel):
    periodo_addnota_inicio: Optional[str] = None
    periodo_addnota_fim: Optional[str] = None
    is_retroativo: Optional[bool] = None
    is_permite_atrasado: Optional[bool] = None
    is_publico_para_grupo: Optional[bool] = None
    canal_chatmessage: Optional[str] = None

class DiarioConfigSummaryResponse(BaseModel):
    id: UUID
    hasRegistroHoje: bool
    grupo: Optional[GrupoResponse] = None

class AnotacaoCreate(BaseModel):
    descricao: str
    id_tarefa: Optional[int] = None
    petrvs_entrega_id: Optional[str] = None
    petrvs_entrega_desc: Optional[str] = None

class DiarioItemCreate(BaseModel):
    is_atrasado: bool = False
    notas: dict[str, list[AnotacaoCreate]]

class DiarioItemUpdate(DiarioItemCreate):
    pass

class AnotacaoResponse(BaseModel):
    id: UUID
    tipo: TipoDiarioItemAnotacaoEnum
    descricao: Optional[str] = None
    id_tarefa: Optional[int] = None
    petrvs_entrega_id: Optional[str] = None
    petrvs_entrega_desc: Optional[str] = None
    inativo: bool

    model_config = ConfigDict(from_attributes=True)

class DiarioItemResponse(BaseModel):
    id: UUID
    data_diario: date
    is_atrasado: bool
    inativo: bool
    atribuicao_usuario: Optional[AtribuicaoResponse] = None
    notas: list[AnotacaoResponse] = []

    model_config = ConfigDict(from_attributes=True)

class DailyReportResponse(BaseModel):
    success: bool
    data: dict[str, list]
