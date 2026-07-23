from uuid import UUID
from typing import Optional
from pydantic import BaseModel, ConfigDict

class AgendamentoCreate(BaseModel):
    tipo: str
    expressao_cron: str
    canal: Optional[str] = None
    mensagem: Optional[str] = None
    inativo: bool = False

class AgendamentoUpdate(BaseModel):
    tipo: Optional[str] = None
    expressao_cron: Optional[str] = None
    canal: Optional[str] = None
    mensagem: Optional[str] = None
    inativo: Optional[bool] = None

class AgendamentoResponse(BaseModel):
    id: UUID
    tipo: str
    expressao_cron: str
    canal: Optional[str] = None
    mensagem: Optional[str] = None
    inativo: bool

    model_config = ConfigDict(from_attributes=True)
