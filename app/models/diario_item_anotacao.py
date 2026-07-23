import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Boolean, DateTime, Integer, Text, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.core.timezone import now_in_app_timezone
from app.models.enums import TipoDiarioItemAnotacaoEnum

if TYPE_CHECKING:
    from app.models.diario_item import DiarioItem


class DiarioItemAnotacao(Base):
    __tablename__ = 'diario_item_anotacoes'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_diario_item: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('diario_items.id'))
    tipo: Mapped[TipoDiarioItemAnotacaoEnum] = mapped_column(SAEnum(TipoDiarioItemAnotacaoEnum), nullable=False)
    descricao: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    id_tarefa: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    petrvs_entrega_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    petrvs_entrega_desc: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    inativo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_in_app_timezone)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    diario_item: Mapped["DiarioItem"] = relationship('DiarioItem', back_populates='notas')
