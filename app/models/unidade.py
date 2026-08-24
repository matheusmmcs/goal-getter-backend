import uuid
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.core.timezone import now_in_app_timezone

if TYPE_CHECKING:
    from app.models.grupo import GrupoTrabalho
    from app.models.perfil import Perfil
    from app.models.organizacao import Organizacao
    from app.models.diario_config import DiarioConfig


class Unidade(Base):
    __tablename__ = 'unidades'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome: Mapped[str] = mapped_column(String, nullable=False)
    nome_ascii: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    sigla: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    codigo: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    id_unidade_pai: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey('unidades.id'), nullable=True)
    id_organizacao: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey('organizacoes.id'), nullable=True)
    campos_customizados: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)
    inativo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_in_app_timezone)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    unidade_pai: Mapped[Optional["Unidade"]] = relationship('Unidade', remote_side=[id])
    organizacao: Mapped[Optional["Organizacao"]] = relationship('Organizacao', back_populates='unidades')
    grupos: Mapped[List["GrupoTrabalho"]] = relationship('GrupoTrabalho', back_populates='unidade')
    perfis: Mapped[List["Perfil"]] = relationship('Perfil', back_populates='unidade')
    diario_configs: Mapped[List["DiarioConfig"]] = relationship('DiarioConfig', back_populates='unidade')

