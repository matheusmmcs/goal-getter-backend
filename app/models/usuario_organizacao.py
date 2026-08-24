import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Enum as SQLEnum, UniqueConstraint, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.core.timezone import now_in_app_timezone
from app.models.enums import PapelOrganizacaoEnum

if TYPE_CHECKING:
    from app.models.usuario import Usuario
    from app.models.organizacao import Organizacao


class UsuarioOrganizacao(Base):
    __tablename__ = 'usuario_organizacoes'
    __table_args__ = (
        UniqueConstraint('id_usuario', 'id_organizacao', name='uq_usuario_organizacao'),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_usuario: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('usuarios.id'), nullable=False)
    id_organizacao: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('organizacoes.id'), nullable=False)
    papel_organizacao: Mapped[PapelOrganizacaoEnum] = mapped_column(
        SQLEnum(PapelOrganizacaoEnum, name='papelorganizacaoenum'),
        default=PapelOrganizacaoEnum.MEMBRO,
        nullable=False
    )
    campos_customizados: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)
    inativo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_in_app_timezone)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    usuario: Mapped["Usuario"] = relationship('Usuario', back_populates='organizacoes_vinculos')
    organizacao: Mapped["Organizacao"] = relationship('Organizacao', back_populates='usuarios_vinculos')
