import re
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import StatusEncomenda

_CODIGO_PADRAO = re.compile(r"^[A-Za-z0-9-]+$")


class EncomendaCriar(BaseModel):
    codigo_rastreio: Annotated[str, Field(min_length=5, max_length=40)]
    descricao: Annotated[str, Field(min_length=1, max_length=200)]
    vendedor: Annotated[str, Field(min_length=1, max_length=120)]

    @field_validator("codigo_rastreio")
    @classmethod
    def normalizar_codigo_rastreio(cls, valor: str) -> str:
        normalizado = valor.strip().upper()
        if not _CODIGO_PADRAO.match(normalizado):
            raise ValueError("Código de rastreio deve conter apenas letras, números e hífen")
        return normalizado

    @field_validator("descricao", "vendedor")
    @classmethod
    def limpar_texto(cls, valor: str) -> str:
        valor_limpo = valor.strip()
        if not valor_limpo:
            raise ValueError("Campo não pode ser vazio")
        return valor_limpo


class EncomendaAtualizar(BaseModel):
    descricao: Annotated[str | None, Field(min_length=1, max_length=200)] = None
    vendedor: Annotated[str | None, Field(min_length=1, max_length=120)] = None

    model_config = {"extra": "forbid"}

    @field_validator("descricao", "vendedor", mode="before")
    @classmethod
    def limpar_texto(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        valor_limpo = valor.strip()
        if not valor_limpo:
            return None
        return valor_limpo

    @model_validator(mode="after")
    def pelo_menos_um_campo(self) -> "EncomendaAtualizar":
        if self.descricao is None and self.vendedor is None:
            raise ValueError("Informe pelo menos descricao ou vendedor")
        return self


class HistoricoStatusLer(BaseModel):
    status_anterior: str | None
    status_novo: str
    ocorrido_em: datetime
    id_evento: str | None = None


class EncomendaLer(BaseModel):
    id: int
    codigo_rastreio: str
    descricao: str
    vendedor: str
    status: StatusEncomenda
    grupo: str
    entregue_em: datetime | None = None
    recebido_por: str | None = None
    criado_em: datetime
    atualizado_em: datetime
    historico: list[HistoricoStatusLer] = []


class EncomendaAdminLer(EncomendaLer):
    usuario_id: int
    usuario_email: str
