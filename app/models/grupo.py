import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.timezone import now_in_app_timezone

class GrupoTrabalho(Base):
    __tablename__ = 'grupos'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome = Column(String, nullable=False)
    id_unidade = Column(UUID(as_uuid=True), ForeignKey('unidades.id'))
    inativo = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now_in_app_timezone)
    updated_at = Column(DateTime, nullable=True)
    ativo = Column(Boolean, default=True)

    unidade = relationship('Unidade', back_populates='grupos')
    atribuicoes = relationship('Atribuicao', back_populates='grupo')
    diario_configs = relationship('DiarioConfig', back_populates='grupo')
