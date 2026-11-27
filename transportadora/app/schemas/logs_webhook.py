from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator


class TentativaWebhookLer(BaseModel):
    numero: int
    status_http: int | None
    erro: str | None
    duracao_ms: int
    tentou_em: datetime


class EventoWebhookLer(BaseModel):
    id: int
    id_evento: str
    tipo_evento: str
    codigo_rastreio: str
    estado: Literal["PENDENTE", "ENVIADO", "FALHA"]
    total_tentativas: int
    ultimo_status_http: int | None
    ultimo_erro: str | None
    criado_em: datetime
    enviado_em: datetime | None
    historico_tentativas: list[TentativaWebhookLer]

    @field_validator("estado")
    @classmethod
    def validar_estado(cls, valor: str) -> str:
        estados_validos = {"PENDENTE", "ENVIADO", "FALHA"}
        if valor not in estados_validos:
            raise ValueError("Estado inválido")
        return valor


class FiltroLogsWebhook(BaseModel):
    codigo_rastreio: str | None = None
    estado: Literal["PENDENTE", "ENVIADO", "FALHA"] | None = None
