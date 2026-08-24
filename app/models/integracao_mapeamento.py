import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.core.timezone import now_in_app_timezone

if TYPE_CHECKING:
    from app.models.integracao_endpoint import IntegracaoEndpoint
    from app.models.meta import Meta
    from app.models.unidade import Unidade


class IntegracaoMapeamento(Base):
    __tablename__ = 'integracoes_mapeamento'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_integracao_endpoint: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey('integracoes_endpoint.id'), nullable=False, unique=True
    )
    items_root_path: Mapped[str] = mapped_column(String, default="$", nullable=False)
    external_id_mode: Mapped[str] = mapped_column(String, default="SIMPLE", nullable=False)
    external_id_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    external_id_composite_paths: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    external_id_composite_template: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    campo_titulo: Mapped[str] = mapped_column(String, nullable=False)
    campo_descricao: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    campo_codigo: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    campo_data_inicio: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    campo_data_fim: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    campo_data_conclusao: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    campo_status: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    map_status_values: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    campo_progresso: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    campo_valor_inicial: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    campo_valor_pretendido: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    campo_valor_atual: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    campo_responsavel: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    campo_tipo_anotacao: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    campo_projeto: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    campo_prioridade: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    campo_autor: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    campo_data_atualizacao: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    campo_link_externo: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    campos_extras: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    campo_meta_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    campo_meta_titulo: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    campo_unidade_origem: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    map_unidades_values: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    map_usuarios_values: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    default_id_meta: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey('metas.id'), nullable=True
    )
    default_id_unidade: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey('unidades.id'), nullable=True
    )
    regras_de_para: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    regras_transformacao: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    inativo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_in_app_timezone)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    endpoint: Mapped["IntegracaoEndpoint"] = relationship(
        'IntegracaoEndpoint', back_populates='mapeamento'
    )
    default_meta: Mapped[Optional["Meta"]] = relationship('Meta')
    default_unidade: Mapped[Optional["Unidade"]] = relationship('Unidade')
