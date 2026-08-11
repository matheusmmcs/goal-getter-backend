import uuid
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.core.timezone import now_in_app_timezone

if TYPE_CHECKING:
    from app.models.usuario_organizacao import UsuarioOrganizacao
    from app.models.unidade import Unidade
    from app.models.grupo import GrupoTrabalho


class Organizacao(Base):
    __tablename__ = 'organizacoes'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome: Mapped[str] = mapped_column(String, nullable=False)
    sigla: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    descricao: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    inativo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_in_app_timezone)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    usuarios_vinculos: Mapped[List["UsuarioOrganizacao"]] = relationship('UsuarioOrganizacao', back_populates='organizacao')
    unidades: Mapped[List["Unidade"]] = relationship('Unidade', back_populates='organizacao')
    grupos: Mapped[List["GrupoTrabalho"]] = relationship('GrupoTrabalho', back_populates='organizacao')
