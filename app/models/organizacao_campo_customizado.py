import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Boolean, DateTime, Text, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.core.timezone import now_in_app_timezone
from app.models.enums import (
    EntidadeCampoCustomizadoEnum,
    TipoDadoCampoCustomizadoEnum,
)

if TYPE_CHECKING:
    from app.models.organizacao import Organizacao


class OrganizacaoCampoCustomizado(Base):
    __tablename__ = 'organizacoes_campos_customizados'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_organizacao: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey('organizacoes.id'), nullable=False, index=True
    )
    entidade: Mapped[EntidadeCampoCustomizadoEnum] = mapped_column(
        SAEnum(EntidadeCampoCustomizadoEnum), nullable=False
    )
    nome_campo: Mapped[str] = mapped_column(String, nullable=False)
    chave: Mapped[str] = mapped_column(String, nullable=False)
    tipo_dado: Mapped[TipoDadoCampoCustomizadoEnum] = mapped_column(
        SAEnum(TipoDadoCampoCustomizadoEnum), default=TipoDadoCampoCustomizadoEnum.TEXTO, nullable=False
    )
    obrigatorio: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    descricao: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    inativo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_in_app_timezone, nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    organizacao: Mapped["Organizacao"] = relationship('Organizacao')
