from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class EventoProcessado(Base):
    __tablename__ = "eventos_processados"

    id_evento: Mapped[str] = mapped_column(String(36), primary_key=True)
    recebido_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
