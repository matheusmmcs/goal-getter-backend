import uuid
from sqlalchemy import Column, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.timezone import now_in_app_timezone

class Atribuicao(Base):
    __tablename__ = 'atribuicoes'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_usuario = Column(UUID(as_uuid=True), ForeignKey('usuarios.id'))
    id_nivel = Column(UUID(as_uuid=True), ForeignKey('niveis.id'))
    id_grupo = Column(UUID(as_uuid=True), ForeignKey('grupos.id'))
    registrador = Column(Boolean, default=False)
    inativo = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now_in_app_timezone)
    updated_at = Column(DateTime, nullable=True)
    ativo = Column(Boolean, default=True)

    usuario = relationship('Usuario', back_populates='atribuicoes')
    nivel = relationship('Nivel')
    grupo = relationship('GrupoTrabalho', back_populates='atribuicoes')
