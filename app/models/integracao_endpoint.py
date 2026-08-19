import uuid
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Boolean, DateTime, Text, ForeignKey, Enum as SAEnum, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.core.timezone import now_in_app_timezone
from app.models.enums import (
    TipoIntegracaoEnum,
    MetodoHttpEnum,
    ModoExecucaoEnum,
)

if TYPE_CHECKING:
    from app.models.integracao_config import IntegracaoConfig
    from app.models.integracao_mapeamento import IntegracaoMapeamento
    from app.models.integracao_execucao_historico import IntegracaoExecucaoHistorico
    from app.models.meta import Meta
    from app.models.entrega import Entrega


class IntegracaoEndpoint(Base):
    __tablename__ = 'integracoes_endpoint'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_integracao_config: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey('integracoes_config.id'), nullable=False
    )
    nome: Mapped[str] = mapped_column(String, nullable=False)
    tipo_integracao: Mapped[TipoIntegracaoEnum] = mapped_column(
        SAEnum(TipoIntegracaoEnum), default=TipoIntegracaoEnum.RECEBER_ENTREGAS, nullable=False
    )
    path: Mapped[str] = mapped_column(String, nullable=False)
    metodo_http: Mapped[MetodoHttpEnum] = mapped_column(
        SAEnum(MetodoHttpEnum), default=MetodoHttpEnum.GET, nullable=False
    )
    modo_execucao: Mapped[ModoExecucaoEnum] = mapped_column(
        SAEnum(ModoExecucaoEnum, values_callable=lambda obj: [e.value for e in obj], name='modoexecucaoenum', create_type=False),
        default=ModoExecucaoEnum.MANUAL_PAINEL,
        nullable=False,
    )
    parametros_config: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    headers_custom: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    corpo_requisicao: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    escopo_unidades: Mapped[Optional[str]] = mapped_column(String, default='TODAS', nullable=True)
    unidades_selecionadas: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    escopo_usuarios: Mapped[Optional[str]] = mapped_column(String, default='TODOS', nullable=True)
    usuarios_selecionados: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    ativo_sincronizacao: Mapped[bool] = mapped_column(Boolean, default=True)
    frequencia_cron: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    inativo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_in_app_timezone)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    integracao_config: Mapped["IntegracaoConfig"] = relationship(
        'IntegracaoConfig', back_populates='endpoints'
    )
    mapeamento: Mapped[Optional["IntegracaoMapeamento"]] = relationship(
        'IntegracaoMapeamento', back_populates='endpoint', uselist=False, cascade='all, delete-orphan'
    )
    historico_execucoes: Mapped[List["IntegracaoExecucaoHistorico"]] = relationship(
        'IntegracaoExecucaoHistorico', back_populates='endpoint', cascade='all, delete-orphan'
    )
    metas: Mapped[List["Meta"]] = relationship('Meta', back_populates='integracao_endpoint')
    entregas: Mapped[List["Entrega"]] = relationship('Entrega', back_populates='integracao_endpoint')
