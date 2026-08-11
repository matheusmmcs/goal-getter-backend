import uuid
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.core.timezone import now_in_app_timezone

if TYPE_CHECKING:
    from app.models.grupo import GrupoTrabalho
    from app.models.unidade import Unidade
    from app.models.diario_item import DiarioItem


class DiarioConfig(Base):
    __tablename__ = 'diario_configs'
    __table_args__ = (
        Index(
            'uix_diario_config_grupo_active',
            'id_grupo',
            unique=True,
            postgresql_where=text("inativo = false AND id_grupo IS NOT NULL"),
            sqlite_where=text("inativo = false AND id_grupo IS NOT NULL")
        ),
        Index(
            'uix_diario_config_unidade_active',
            'id_unidade',
            unique=True,
            postgresql_where=text("inativo = false AND id_unidade IS NOT NULL"),
            sqlite_where=text("inativo = false AND id_unidade IS NOT NULL")
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_grupo: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey('grupos.id'), nullable=True)
    id_unidade: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey('unidades.id'), nullable=True)
    periodo_addnota_inicio: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    periodo_addnota_fim: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_retroativo: Mapped[bool] = mapped_column(Boolean, default=False)
    is_permite_atrasado: Mapped[bool] = mapped_column(Boolean, default=False)
    is_publico_para_grupo: Mapped[bool] = mapped_column(Boolean, default=True)
    canal_chatmessage: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    inativo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_in_app_timezone)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    grupo: Mapped[Optional["GrupoTrabalho"]] = relationship('GrupoTrabalho', back_populates='diario_configs')
    unidade: Mapped[Optional["Unidade"]] = relationship('Unidade', back_populates='diario_configs')
    items: Mapped[List["DiarioItem"]] = relationship('DiarioItem', back_populates='config')
