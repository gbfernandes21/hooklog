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
from app.models.enums import StatusEncomenda

if TYPE_CHECKING:
    from app.models.historico_status import HistoricoStatus
    from app.models.usuario import Usuario

_VALORES_STATUS = ", ".join(f"'{status.value}'" for status in StatusEncomenda)


class Encomenda(Base):
    __tablename__ = "encomendas"
    __table_args__ = (
        CheckConstraint(f"status IN ({_VALORES_STATUS})", name="status_valido"),
        Index("ix_encomendas_usuario_id_status", "usuario_id", "status"),
        Index("ix_encomendas_status_proxima_tentativa_em", "status", "proxima_tentativa_em"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False
    )
    usuario: Mapped[Usuario] = relationship(back_populates="encomendas")
    codigo_rastreio: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    descricao: Mapped[str] = mapped_column(String(200), nullable=False)
    vendedor: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    tentativas_registro: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    proxima_tentativa_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ultimo_erro_registro: Mapped[str | None] = mapped_column(Text, nullable=True)
    entregue_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recebido_por: Mapped[str | None] = mapped_column(String(120), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    historico: Mapped[list[HistoricoStatus]] = relationship(
        back_populates="encomenda",
        cascade="all, delete-orphan",
        order_by="HistoricoStatus.ocorrido_em",
    )
