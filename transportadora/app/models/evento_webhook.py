from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import EstadoEnvio

if TYPE_CHECKING:
    from app.models.remessa import Remessa
    from app.models.tentativa_webhook import TentativaWebhook

_VALORES_ESTADO = ", ".join(f"'{estado.value}'" for estado in EstadoEnvio)


class EventoWebhook(Base):
    __tablename__ = "eventos_webhook"
    __table_args__ = (
        CheckConstraint(f"estado IN ({_VALORES_ESTADO})", name="estado_valido"),
        Index("ix_eventos_webhook_estado_proxima_tentativa_em", "estado", "proxima_tentativa_em"),
        Index("ix_eventos_webhook_remessa_id_id", "remessa_id", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    remessa_id: Mapped[int] = mapped_column(
        ForeignKey("remessas.id", ondelete="CASCADE"), nullable=False
    )
    id_evento: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    tipo_evento: Mapped[str] = mapped_column(String(40), nullable=False)
    corpo: Mapped[str] = mapped_column(Text, nullable=False)
    estado: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default=text("'PENDENTE'")
    )
    total_tentativas: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    proxima_tentativa_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ultimo_status_http: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ultimo_erro: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    enviado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    remessa: Mapped[Remessa] = relationship(back_populates="eventos_webhook")
    tentativas: Mapped[list[TentativaWebhook]] = relationship(
        back_populates="evento_webhook",
        cascade="all, delete-orphan",
        order_by="TentativaWebhook.numero",
    )
