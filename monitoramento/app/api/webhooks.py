from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.banco_dados import obter_sessao
from app.core.configuracao import Configuracao
from app.core.dependencias import obter_configuracao_atual, obter_relogio
from app.core.erros import ErroDeDominio
from app.schemas.webhook import EventoWebhook
from app.services.servico_webhook import ServicoWebhook
from app.services.verificador_hmac import verificar

roteador = APIRouter(tags=["webhooks"])


@roteador.post("/webhooks/transportadora")
async def receber_webhook(
    request: Request,
    sessao: Annotated[AsyncSession, Depends(obter_sessao)],
    configuracao: Annotated[Configuracao, Depends(obter_configuracao_atual)],
    agora: Annotated[datetime, Depends(obter_relogio)],
    x_carimbo_tempo: Annotated[str | None, Header()] = None,
    x_assinatura: Annotated[str | None, Header()] = None,
) -> dict[str, str]:
    if x_carimbo_tempo is None or x_assinatura is None:
        raise ErroDeDominio(
            "Assinatura invalida", "ASSINATURA_INVALIDA", status.HTTP_401_UNAUTHORIZED
        )

    corpo_bruto = await request.body()

    valida = verificar(
        segredo=configuracao.segredo_webhook,
        carimbo_tempo=x_carimbo_tempo,
        assinatura=x_assinatura,
        corpo_bruto=corpo_bruto,
        agora=agora,
        tolerancia_segundos=configuracao.tolerancia_timestamp_webhook_segundos,
    )
    if not valida:
        raise ErroDeDominio(
            "Assinatura invalida", "ASSINATURA_INVALIDA", status.HTTP_401_UNAUTHORIZED
        )

    try:
        evento = EventoWebhook.model_validate_json(corpo_bruto)
    except ValidationError as erro:
        raise ErroDeDominio("Corpo do evento invalido", "CORPO_INVALIDO", 422) from erro

    servico = ServicoWebhook(sessao)
    resultado = await servico.aplicar_evento(evento, agora)
    return {"resultado": resultado}
