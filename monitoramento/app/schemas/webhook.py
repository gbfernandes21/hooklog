from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from app.models.enums import StatusEncomenda

_TIPOS_EVENTO = {"remessa.status_alterado", "remessa.entregue"}


class EventoWebhook(BaseModel):
    id_evento: Annotated[str, Field(min_length=1, max_length=36)]
    tipo_evento: Annotated[str, Field(min_length=1, max_length=40)]
    codigo_rastreio: Annotated[str, Field(min_length=1, max_length=40)]
    status: Annotated[str, Field(min_length=1, max_length=20)]
    vendedor: Annotated[str, Field(min_length=1, max_length=120)]
    ocorrido_em: datetime
    entregue_em: datetime | None = None
    recebido_por: str | None = None

    @field_validator("tipo_evento")
    @classmethod
    def validar_tipo_evento(cls, valor: str) -> str:
        if valor not in _TIPOS_EVENTO:
            raise ValueError("tipo_evento deve ser remessa.status_alterado ou remessa.entregue")
        return valor

    @field_validator("status")
    @classmethod
    def validar_status(cls, valor: str) -> str:
        valores = {membro.value for membro in StatusEncomenda}
        if valor not in valores:
            raise ValueError("status invalido")
        return valor
