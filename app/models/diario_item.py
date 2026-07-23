import uuid
from datetime import datetime, date
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import Boolean, DateTime, Date, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.core.timezone import now_in_app_timezone

if TYPE_CHECKING:
    from app.models.diario_config import DiarioConfig
    from app.models.atribuicao import Atribuicao
    from app.models.diario_item_anotacao import DiarioItemAnotacao


class DiarioItem(Base):
    __tablename__ = 'diario_items'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_diario_config: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('diario_configs.id'))
    id_atribuicao_usuario: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('atribuicoes.id'))
    data_diario: Mapped[date] = mapped_column(Date, nullable=False)
    is_atrasado: Mapped[bool] = mapped_column(Boolean, default=False)
    inativo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_in_app_timezone)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    config: Mapped["DiarioConfig"] = relationship('DiarioConfig', back_populates='items')
    atribuicao_usuario: Mapped["Atribuicao"] = relationship('Atribuicao')
    notas: Mapped[List["DiarioItemAnotacao"]] = relationship('DiarioItemAnotacao', back_populates='diario_item')
