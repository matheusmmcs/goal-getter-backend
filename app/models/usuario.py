import uuid
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.core.timezone import now_in_app_timezone

if TYPE_CHECKING:
    from app.models.perfil import Perfil
    from app.models.atribuicao import Atribuicao


class Usuario(Base):
    __tablename__ = 'usuarios'

    # Columns to exclude from default JSON serialization
    __json_exclude__ = {'senha'}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    senha: Mapped[str] = mapped_column(String, nullable=False)
    nome: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    cpf: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_autorizado: Mapped[bool] = mapped_column(Boolean, default=False)
    inativo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_in_app_timezone)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    perfis: Mapped[List["Perfil"]] = relationship('Perfil', back_populates='usuario')
    atribuicoes: Mapped[List["Atribuicao"]] = relationship('Atribuicao', back_populates='usuario')

    def __iter__(self):
        """Custom iterator that excludes senha from dict() serialization."""
        for key in self.__table__.columns.keys():
            if key not in self.__json_exclude__:
                yield key, getattr(self, key)
