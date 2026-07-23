from uuid import UUID
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.schemas.unidade import UnidadeResponse
from app.schemas.nivel import NivelResponse

class PerfilResponse(BaseModel):
    id: UUID
    inativo: bool
    unidade: Optional[UnidadeResponse] = None
    nivel: Optional[NivelResponse] = None

    model_config = ConfigDict(from_attributes=True)
