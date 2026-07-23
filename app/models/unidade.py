import uuid
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.timezone import now_in_app_timezone

class Unidade(Base):
    __tablename__ = 'unidades'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome = Column(String, nullable=False)
    nome_ascii = Column(String)
    sigla = Column(String)
    codigo = Column(Integer)
    id_unidade_pai = Column(UUID(as_uuid=True), ForeignKey('unidades.id'), nullable=True)
    inativo = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now_in_app_timezone)
    updated_at = Column(DateTime, nullable=True)
    ativo = Column(Boolean, default=True)

    unidade_pai = relationship('Unidade', remote_side=[id])
    grupos = relationship('GrupoTrabalho', back_populates='unidade')
    perfis = relationship('Perfil', back_populates='unidade')
