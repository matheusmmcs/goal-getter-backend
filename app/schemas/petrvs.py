from uuid import UUID
from typing import Optional, Any
from pydantic import BaseModel, ConfigDict

class PetrvsEntregaResponse(BaseModel):
    id: str
    descricao: str
    plano_trabalho_data_inicio: Optional[str] = None
    plano_trabalho_data_fim: Optional[str] = None

    model_config = ConfigDict(extra='allow', from_attributes=True)

class PetrvsResponse(BaseModel):
    success: bool
    data: list[PetrvsEntregaResponse]
