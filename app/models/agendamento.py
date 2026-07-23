import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.timezone import now_in_app_timezone

class Agendamento(Base):
    __tablename__ = 'agendamentos'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tipo = Column(String)
    expressao_cron = Column(String)
    canal = Column(String)
    mensagem = Column(Text)
    id_usuario_criador = Column(UUID(as_uuid=True), ForeignKey('usuarios.id'), nullable=True)
    inativo = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now_in_app_timezone)
    updated_at = Column(DateTime, nullable=True)
    ativo = Column(Boolean, default=True)
