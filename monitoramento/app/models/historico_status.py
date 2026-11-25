from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Identity, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.encomenda import Encomenda


class HistoricoStatus(Base):
    __tablename__ = "historico_status"
    __table_args__ = (
        Index("ix_historico_status_encomenda_id_ocorrido_em", "encomenda_id", "ocorrido_em"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    encomenda_id: Mapped[int] = mapped_column(
        ForeignKey("encomendas.id", ondelete="CASCADE"), nullable=False
    )
    status_anterior: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status_novo: Mapped[str] = mapped_column(String(20), nullable=False)
    id_evento: Mapped[str | None] = mapped_column(String(36), unique=True, nullable=True)
    ocorrido_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    registrado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    encomenda: Mapped[Encomenda] = relationship(back_populates="historico")
