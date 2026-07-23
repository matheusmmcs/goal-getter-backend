import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from app.core.timezone import now_in_app_timezone

class Agendamento(Base):
    __tablename__ = 'agendamentos'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tipo: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    expressao_cron: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    canal: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    mensagem: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    id_usuario_criador: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey('usuarios.id'), nullable=True)
    inativo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_in_app_timezone)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=False)
