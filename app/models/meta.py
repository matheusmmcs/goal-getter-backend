import uuid
from datetime import datetime, date
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Boolean, DateTime, Date, Numeric, Text, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.core.timezone import now_in_app_timezone
from app.models.enums import MetaStatusEnum, OrigemPlanejamentoEnum

if TYPE_CHECKING:
    from app.models.organizacao import Organizacao
    from app.models.unidade import Unidade
    from app.models.entrega import Entrega


class Meta(Base):
    __tablename__ = 'metas'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_organizacao: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('organizacoes.id'), nullable=False)
    id_unidade: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey('unidades.id'), nullable=True)
    titulo: Mapped[str] = mapped_column(String, nullable=False)
    descricao: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    codigo: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    valor_meta_inicial: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)
    valor_meta_pretendida: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)
    valor_meta_atual: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)
    data_inicio: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    data_fim: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[MetaStatusEnum] = mapped_column(SAEnum(MetaStatusEnum), default=MetaStatusEnum.PLANEJADA)
    tipo_origem: Mapped[OrigemPlanejamentoEnum] = mapped_column(SAEnum(OrigemPlanejamentoEnum), default=OrigemPlanejamentoEnum.INTERNA)
    inativo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_in_app_timezone)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    organizacao: Mapped["Organizacao"] = relationship('Organizacao')
    unidade: Mapped[Optional["Unidade"]] = relationship('Unidade')
    entregas: Mapped[List["Entrega"]] = relationship('Entrega', back_populates='meta')
