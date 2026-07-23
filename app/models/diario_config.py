import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.timezone import now_in_app_timezone

class DiarioConfig(Base):
    __tablename__ = 'diario_configs'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_grupo = Column(UUID(as_uuid=True), ForeignKey('grupos.id'))
    periodo_addnota_inicio = Column(String)
    periodo_addnota_fim = Column(String)
    is_retroativo = Column(Boolean, default=False)
    is_permite_atrasado = Column(Boolean, default=False)
    is_publico_para_grupo = Column(Boolean, default=True)
    canal_chatmessage = Column(String)
    inativo = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now_in_app_timezone)
    updated_at = Column(DateTime, nullable=True)
    ativo = Column(Boolean, default=True)

    grupo = relationship('GrupoTrabalho', back_populates='diario_configs')
    items = relationship('DiarioItem', back_populates='config')
