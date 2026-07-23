import uuid
from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.timezone import now_in_app_timezone


class Usuario(Base):
    __tablename__ = 'usuarios'

    # Columns to exclude from default JSON serialization
    __json_exclude__ = {'senha'}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario = Column(String, unique=True, nullable=False)
    senha = Column(String, nullable=False)
    nome = Column(String, nullable=False)
    email = Column(String)
    cpf = Column(String)
    is_admin = Column(Boolean, default=False)
    is_autorizado = Column(Boolean, default=False)
    inativo = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now_in_app_timezone)
    updated_at = Column(DateTime, nullable=True)
    ativo = Column(Boolean, default=True)

    perfis = relationship('Perfil', back_populates='usuario')
    atribuicoes = relationship('Atribuicao', back_populates='usuario')

    def __iter__(self):
        """Custom iterator that excludes senha from dict() serialization."""
        for key in self.__table__.columns.keys():
            if key not in self.__json_exclude__:
                yield key, getattr(self, key)

