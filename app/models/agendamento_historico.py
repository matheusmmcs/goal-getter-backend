import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from app.core.timezone import now_in_app_timezone

class AgendamentoHistorico(Base):
    __tablename__ = 'agendamentos_historico'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_agendamento: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('agendamentos.id'))
    data_envio: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    sucesso: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    detalhes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_in_app_timezone)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
