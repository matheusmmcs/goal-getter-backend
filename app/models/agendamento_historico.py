import uuid
from sqlalchemy import Column, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
from app.core.timezone import now_in_app_timezone

class AgendamentoHistorico(Base):
    __tablename__ = 'agendamentos_historico'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_agendamento = Column(UUID(as_uuid=True), ForeignKey('agendamentos.id'))
    data_envio = Column(DateTime)
    sucesso = Column(Boolean)
    detalhes = Column(Text)
    created_at = Column(DateTime, default=now_in_app_timezone)
    updated_at = Column(DateTime, nullable=True)
    ativo = Column(Boolean, default=True)
