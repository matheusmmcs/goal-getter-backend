import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.core.timezone import now_in_app_timezone

if TYPE_CHECKING:
    from app.models.usuario import Usuario
    from app.models.unidade import Unidade
    from app.models.nivel import Nivel


class Perfil(Base):
    __tablename__ = 'perfis'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_usuario: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('usuarios.id'))
    id_unidade: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('unidades.id'))
    id_nivel: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('niveis.id'))
    inativo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_in_app_timezone)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    usuario: Mapped["Usuario"] = relationship('Usuario', back_populates='perfis')
    unidade: Mapped["Unidade"] = relationship('Unidade', back_populates='perfis')
    nivel: Mapped["Nivel"] = relationship('Nivel')
