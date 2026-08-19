import uuid
from datetime import datetime, date
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Boolean, DateTime, Date, Integer, Text, ForeignKey, Enum as SAEnum, JSON, Index, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.core.timezone import now_in_app_timezone
from app.models.enums import EntregaStatusEnum, OrigemEntregaEnum

if TYPE_CHECKING:
    from app.models.organizacao import Organizacao
    from app.models.unidade import Unidade
    from app.models.usuario import Usuario
    from app.models.meta import Meta
    from app.models.diario_item_anotacao import DiarioItemAnotacao
    from app.models.integracao_config import IntegracaoConfig
    from app.models.integracao_endpoint import IntegracaoEndpoint


class Entrega(Base):
    __tablename__ = 'entregas'
    __table_args__ = (
        Index(
            'uix_entrega_external_sync',
            'id_integracao_config', 'external_id',
            unique=True,
            postgresql_where=text("inativo = false AND external_id IS NOT NULL AND id_integracao_config IS NOT NULL"),
            sqlite_where=text("inativo = false AND external_id IS NOT NULL AND id_integracao_config IS NOT NULL")
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_organizacao: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('organizacoes.id'), nullable=False)
    id_meta: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey('metas.id'), nullable=True)
    id_unidade: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey('unidades.id'), nullable=True)
    id_usuario_responsavel: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey('usuarios.id'), nullable=True)
    id_integracao_config: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey('integracoes_config.id'), nullable=True
    )
    id_integracao_endpoint: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey('integracoes_endpoint.id'), nullable=True
    )
    external_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    titulo: Mapped[str] = mapped_column(String, nullable=False)
    descricao: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tipo_origem: Mapped[OrigemEntregaEnum] = mapped_column(SAEnum(OrigemEntregaEnum), default=OrigemEntregaEnum.INTERNA)
    data_inicio: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    data_fim: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    data_conclusao: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[EntregaStatusEnum] = mapped_column(SAEnum(EntregaStatusEnum), default=EntregaStatusEnum.NAO_INICIADA)
    progresso_percentual: Mapped[int] = mapped_column(Integer, default=0)
    external_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    inativo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_in_app_timezone)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    organizacao: Mapped["Organizacao"] = relationship('Organizacao')
    meta: Mapped[Optional["Meta"]] = relationship('Meta', back_populates='entregas')
    unidade: Mapped[Optional["Unidade"]] = relationship('Unidade')
    usuario_responsavel: Mapped[Optional["Usuario"]] = relationship('Usuario')
    integracao_config: Mapped[Optional["IntegracaoConfig"]] = relationship('IntegracaoConfig', back_populates='entregas')
    integracao_endpoint: Mapped[Optional["IntegracaoEndpoint"]] = relationship('IntegracaoEndpoint', back_populates='entregas')
    anotacoes_diario: Mapped[List["DiarioItemAnotacao"]] = relationship('DiarioItemAnotacao', back_populates='entrega')
