import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.timezone import now_in_app_timezone
from app.models.enums import TipoDiarioItemAnotacaoEnum

class DiarioItemAnotacao(Base):
    __tablename__ = 'diario_item_anotacoes'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_diario_item = Column(UUID(as_uuid=True), ForeignKey('diario_items.id'))
    tipo = Column(SAEnum(TipoDiarioItemAnotacaoEnum), nullable=False)
    descricao = Column(Text)
    id_tarefa = Column(Integer, nullable=True)
    petrvs_entrega_id = Column(String)
    petrvs_entrega_desc = Column(String)
    inativo = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now_in_app_timezone)
    updated_at = Column(DateTime, nullable=True)
    ativo = Column(Boolean, default=True)

    diario_item = relationship('DiarioItem', back_populates='notas')
