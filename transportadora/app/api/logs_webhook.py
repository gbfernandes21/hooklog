from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.banco_dados import obter_sessao
from app.core.dependencias import exigir_admin
from app.schemas.logs_webhook import EventoWebhookLer, FiltroLogsWebhook
from app.services.servico_logs_webhook import ServicoLogsWebhook

roteador = APIRouter(prefix="/logs-webhook", tags=["logs de webhook"])


@roteador.get("", response_model=list[EventoWebhookLer])
async def listar_logs_webhook(
    filtro: Annotated[FiltroLogsWebhook, Depends()],
    _credencial: Annotated[None, Depends(exigir_admin)] = None,
    sessao: Annotated[AsyncSession, Depends(obter_sessao)] = None,
) -> list[EventoWebhookLer]:
    servico = ServicoLogsWebhook(sessao)
    return await servico.listar(
        codigo_rastreio=filtro.codigo_rastreio,
        estado=filtro.estado,
    )


@roteador.post("/{id}/reenviar", response_model=EventoWebhookLer, status_code=202)
async def reenviar_log_webhook(
    id: Annotated[int, Path()],
    _credencial: Annotated[None, Depends(exigir_admin)],
    sessao: Annotated[AsyncSession, Depends(obter_sessao)],
) -> EventoWebhookLer:
    servico = ServicoLogsWebhook(sessao)
    return await servico.reenviar(
        evento_id=id,
        agora=datetime.now(UTC),
    )
