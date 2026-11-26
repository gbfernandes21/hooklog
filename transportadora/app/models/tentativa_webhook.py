from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Identity, Index, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.evento_webhook import EventoWebhook


class TentativaWebhook(Base):
    __tablename__ = "tentativas_webhook"
    __table_args__ = (
        Index("ix_tentativas_webhook_evento_webhook_id_numero", "evento_webhook_id", "numero"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    evento_webhook_id: Mapped[int] = mapped_column(
        ForeignKey("eventos_webhook.id", ondelete="CASCADE"), nullable=False
    )
    numero: Mapped[int] = mapped_column(Integer, nullable=False)
    status_http: Mapped[int | None] = mapped_column(Integer, nullable=True)
    erro: Mapped[str | None] = mapped_column(Text, nullable=True)
    duracao_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    tentou_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    evento_webhook: Mapped[EventoWebhook] = relationship(back_populates="tentativas")
