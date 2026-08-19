import uuid
from datetime import datetime, date
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Boolean, DateTime, Date, Numeric, Text, ForeignKey, Enum as SAEnum, JSON, Index, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.core.timezone import now_in_app_timezone
from app.models.enums import MetaStatusEnum, OrigemPlanejamentoEnum

if TYPE_CHECKING:
    from app.models.organizacao import Organizacao
    from app.models.unidade import Unidade
    from app.models.entrega import Entrega
    from app.models.integracao_config import IntegracaoConfig
    from app.models.integracao_endpoint import IntegracaoEndpoint


class Meta(Base):
    __tablename__ = 'metas'
    __table_args__ = (
        Index(
            'uix_meta_external_sync',
            'id_integracao_config', 'external_id',
            unique=True,
            postgresql_where=text("inativo = false AND external_id IS NOT NULL AND id_integracao_config IS NOT NULL"),
            sqlite_where=text("inativo = false AND external_id IS NOT NULL AND id_integracao_config IS NOT NULL")
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_organizacao: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('organizacoes.id'), nullable=False)
    id_unidade: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey('unidades.id'), nullable=True)
    id_integracao_config: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey('integracoes_config.id'), nullable=True
    )
    id_integracao_endpoint: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey('integracoes_endpoint.id'), nullable=True
    )
    external_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
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
    external_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    inativo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_in_app_timezone)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    organizacao: Mapped["Organizacao"] = relationship('Organizacao')
    unidade: Mapped[Optional["Unidade"]] = relationship('Unidade')
    integracao_config: Mapped[Optional["IntegracaoConfig"]] = relationship('IntegracaoConfig', back_populates='metas')
    integracao_endpoint: Mapped[Optional["IntegracaoEndpoint"]] = relationship('IntegracaoEndpoint', back_populates='metas')
    entregas: Mapped[List["Entrega"]] = relationship('Entrega', back_populates='meta')
