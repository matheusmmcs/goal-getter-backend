import uuid
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.core.timezone import now_in_app_timezone

if TYPE_CHECKING:
    from app.models.unidade import Unidade
    from app.models.atribuicao import Atribuicao
    from app.models.diario_config import DiarioConfig


class GrupoTrabalho(Base):
    __tablename__ = 'grupos'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome: Mapped[str] = mapped_column(String, nullable=False)
    id_unidade: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('unidades.id'))
    inativo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_in_app_timezone)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    unidade: Mapped["Unidade"] = relationship('Unidade', back_populates='grupos')
    atribuicoes: Mapped[List["Atribuicao"]] = relationship('Atribuicao', back_populates='grupo')
    diario_configs: Mapped[List["DiarioConfig"]] = relationship('DiarioConfig', back_populates='grupo')
