import uuid
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
from app.core.timezone import now_in_app_timezone
from app.models.enums import TipoNivelEnum

class Nivel(Base):
    __tablename__ = 'niveis'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome = Column(String, nullable=False)
    tipo = Column(SAEnum(TipoNivelEnum), nullable=False)
    valor = Column(Integer, unique=True, nullable=False)
    inativo = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now_in_app_timezone)
    updated_at = Column(DateTime, nullable=True)
    ativo = Column(Boolean, default=True)
