import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import Integer, Boolean, DateTime, ForeignKey, Enum as SAEnum, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.core.timezone import now_in_app_timezone
from app.models.enums import StatusExecucaoEnum, OrigemDisparoEnum

if TYPE_CHECKING:
    from app.models.integracao_config import IntegracaoConfig
    from app.models.integracao_endpoint import IntegracaoEndpoint
    from app.models.usuario import Usuario


class IntegracaoExecucaoHistorico(Base):
    __tablename__ = 'integracoes_execucao_historico'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_integracao_config: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey('integracoes_config.id'), nullable=False
    )
    id_integracao_endpoint: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey('integracoes_endpoint.id'), nullable=True
    )
    data_inicio: Mapped[datetime] = mapped_column(DateTime, default=now_in_app_timezone, nullable=False)
    data_fim: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[StatusExecucaoEnum] = mapped_column(
        SAEnum(StatusExecucaoEnum), default=StatusExecucaoEnum.EM_ANDAMENTO, nullable=False
    )
    total_encontrados: Mapped[int] = mapped_column(Integer, default=0)
    total_criados: Mapped[int] = mapped_column(Integer, default=0)
    total_atualizados: Mapped[int] = mapped_column(Integer, default=0)
    total_inalterados: Mapped[int] = mapped_column(Integer, default=0)
    total_erros: Mapped[int] = mapped_column(Integer, default=0)
    log_detalhes: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    disparado_por: Mapped[OrigemDisparoEnum] = mapped_column(
        SAEnum(OrigemDisparoEnum), default=OrigemDisparoEnum.MANUAL, nullable=False
    )
    id_usuario_executor: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey('usuarios.id'), nullable=True
    )
    inativo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_in_app_timezone)

    integracao_config: Mapped["IntegracaoConfig"] = relationship(
        'IntegracaoConfig', back_populates='historico_execucoes'
    )
    endpoint: Mapped[Optional["IntegracaoEndpoint"]] = relationship(
        'IntegracaoEndpoint', back_populates='historico_execucoes'
    )
    usuario_executor: Mapped[Optional["Usuario"]] = relationship('Usuario')
