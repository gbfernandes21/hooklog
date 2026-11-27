import re
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

from app.models.enums import StatusRemessa

_CODIGO_PADRAO = re.compile(r"^[A-Za-z0-9-]+$")


class RemessaCriar(BaseModel):
    codigo_rastreio: Annotated[str, Field(min_length=5, max_length=40)]
    vendedor: Annotated[str, Field(min_length=1, max_length=120)]
    url_callback: Annotated[str, Field(min_length=1, max_length=500)]

    @field_validator("codigo_rastreio")
    @classmethod
    def normalizar_codigo_rastreio(cls, valor: str) -> str:
        normalizado = valor.strip().upper()
        if not _CODIGO_PADRAO.match(normalizado):
            raise ValueError("Código de rastreio deve conter apenas letras, números e hífen")
        return normalizado

    @field_validator("vendedor", "url_callback")
    @classmethod
    def limpar_texto(cls, valor: str) -> str:
        valor_limpo = valor.strip()
        if not valor_limpo:
            raise ValueError("Campo não pode ser vazio")
        return valor_limpo


class RemessaStatusAtualizar(BaseModel):
    status: Literal["POSTADO", "EM_TRANSITO", "SAIU_PARA_ENTREGA"]


class RemessaEntregar(BaseModel):
    recebido_por: Annotated[str | None, Field(max_length=120)] = None

    @field_validator("recebido_por")
    @classmethod
    def limpar_recebido_por(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        valor_limpo = valor.strip()
        return valor_limpo or None


class RemessaLer(BaseModel):
    id: int
    codigo_rastreio: str
    vendedor: str
    status: StatusRemessa
    proximo_status: StatusRemessa | None
    url_callback: str
    entregue_em: datetime | None
    recebido_por: str | None
    criado_em: datetime
    atualizado_em: datetime
