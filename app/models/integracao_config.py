import uuid
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Boolean, DateTime, Text, ForeignKey, Enum as SAEnum, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.core.timezone import now_in_app_timezone
from app.models.enums import (
    ProvedorIntegracaoEnum,
    TipoAutenticacaoEnum,
    MetodoHttpEnum,
)

if TYPE_CHECKING:
    from app.models.organizacao import Organizacao
    from app.models.agendamento import Agendamento
    from app.models.integracao_endpoint import IntegracaoEndpoint
    from app.models.integracao_execucao_historico import IntegracaoExecucaoHistorico
    from app.models.meta import Meta
    from app.models.entrega import Entrega


class IntegracaoConfig(Base):
    __tablename__ = 'integracoes_config'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_organizacao: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('organizacoes.id'), nullable=False)
    nome: Mapped[str] = mapped_column(String, nullable=False)
    descricao: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    provedor: Mapped[ProvedorIntegracaoEnum] = mapped_column(
        SAEnum(ProvedorIntegracaoEnum), default=ProvedorIntegracaoEnum.CUSTOM_REST, nullable=False
    )
    url_base: Mapped[str] = mapped_column(String, nullable=False)
    tipo_autenticacao: Mapped[TipoAutenticacaoEnum] = mapped_column(
        SAEnum(TipoAutenticacaoEnum), default=TipoAutenticacaoEnum.NONE, nullable=False
    )
    auth_endpoint_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    auth_metodo_http: Mapped[Optional[MetodoHttpEnum]] = mapped_column(
        SAEnum(MetodoHttpEnum), default=MetodoHttpEnum.POST, nullable=True
    )
    auth_headers: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    auth_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    auth_token_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    auth_static_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    headers_padrao: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ativo_sincronizacao: Mapped[bool] = mapped_column(Boolean, default=True)
    frequencia_cron: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    id_agendamento: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey('agendamentos.id'), nullable=True
    )
    inativo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_in_app_timezone)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    organizacao: Mapped["Organizacao"] = relationship('Organizacao')
    agendamento: Mapped[Optional["Agendamento"]] = relationship('Agendamento')
    endpoints: Mapped[List["IntegracaoEndpoint"]] = relationship(
        'IntegracaoEndpoint', back_populates='integracao_config', cascade='all, delete-orphan'
    )
    historico_execucoes: Mapped[List["IntegracaoExecucaoHistorico"]] = relationship(
        'IntegracaoExecucaoHistorico', back_populates='integracao_config', cascade='all, delete-orphan'
    )
    metas: Mapped[List["Meta"]] = relationship('Meta', back_populates='integracao_config')
    entregas: Mapped[List["Entrega"]] = relationship('Entrega', back_populates='integracao_config')
