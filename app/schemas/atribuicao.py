from uuid import UUID
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.schemas.nivel import NivelResponse
from app.schemas.grupo import GrupoResponse

class AtribuicaoResponse(BaseModel):
    id: UUID
    id_usuario: UUID
    id_grupo: UUID
    inativo: bool
    registrador: bool
    usuario: Optional[dict] = None  # To prevent circular import issues
    nivel: Optional[NivelResponse] = None
    grupo: Optional[GrupoResponse] = None

    model_config = ConfigDict(from_attributes=True)
