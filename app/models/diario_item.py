import uuid
from sqlalchemy import Column, Boolean, DateTime, Date, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.timezone import now_in_app_timezone

class DiarioItem(Base):
    __tablename__ = 'diario_items'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_diario_config = Column(UUID(as_uuid=True), ForeignKey('diario_configs.id'))
    id_atribuicao_usuario = Column(UUID(as_uuid=True), ForeignKey('atribuicoes.id'))
    data_diario = Column(Date, nullable=False)
    is_atrasado = Column(Boolean, default=False)
    inativo = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now_in_app_timezone)
    updated_at = Column(DateTime, nullable=True)
    ativo = Column(Boolean, default=True)

    config = relationship('DiarioConfig', back_populates='items')
    atribuicao_usuario = relationship('Atribuicao')
    notas = relationship('DiarioItemAnotacao', back_populates='diario_item')
