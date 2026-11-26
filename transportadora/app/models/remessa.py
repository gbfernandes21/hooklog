from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Identity,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import StatusRemessa

if TYPE_CHECKING:
    from app.models.evento_webhook import EventoWebhook

_VALORES_STATUS = ", ".join(f"'{status.value}'" for status in StatusRemessa)


class Remessa(Base):
    __tablename__ = "remessas"
    __table_args__ = (CheckConstraint(f"status IN ({_VALORES_STATUS})", name="status_valido"),)

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    codigo_rastreio: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    vendedor: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'AGUARDANDO_ENVIO'")
    )
    url_callback: Mapped[str] = mapped_column(String(500), nullable=False)
    entregue_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recebido_por: Mapped[str | None] = mapped_column(String(120), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    eventos_webhook: Mapped[list[EventoWebhook]] = relationship(
        back_populates="remessa",
        cascade="all, delete-orphan",
        order_by="EventoWebhook.id",
    )
