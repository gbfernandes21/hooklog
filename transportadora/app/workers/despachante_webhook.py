import asyncio
import logging
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.core.configuracao import Configuracao, obter_configuracao
from app.models.evento_webhook import EventoWebhook
from app.repositories.repositorio_evento_webhook import RepositorioEventoWebhook
from app.workers.enviador_webhook import EnviadorWebhook

logger = logging.getLogger(__name__)

LIMITE_LOTE_WEBHOOK = 20


async def processar_evento(
    sessao: AsyncSession,
    evento: EventoWebhook,
    enviador: EnviadorWebhook,
    agora: datetime,
) -> None:
    repositorio = RepositorioEventoWebhook(sessao)
    resultado = await enviador.enviar_evento(evento, agora)

    tentativa_numero = evento.total_tentativas + 1
    await repositorio.criar_tentativa(
        evento_webhook_id=evento.id,
        numero=tentativa_numero,
        status_http=resultado.status_http,
        erro=resultado.erro,
        duracao_ms=0,
        tentou_em=agora,
    )

    if resultado.enviado:
        await repositorio.marcar_enviado(evento, agora)
        logger.info(
            "Evento %s enviado com sucesso para a remessa %s",
            evento.id_evento,
            evento.remessa.codigo_rastreio,
        )
        return

    proxima_tentativa = evento.total_tentativas + 1
    if (
        resultado.falha_permanente
        or proxima_tentativa >= enviador._configuracao.max_tentativas_webhook
    ):
        await repositorio.marcar_falha_definitiva(
            evento,
            total_tentativas=proxima_tentativa,
            proxima_tentativa_em=agora,
            ultimo_status_http=resultado.status_http,
            ultimo_erro=resultado.erro,
        )
        logger.warning(
            "Evento %s falhou definitivamente (tentativa %d): %s",
            evento.id_evento,
            proxima_tentativa,
            resultado.erro,
        )
        return

    proxima_em = agora + timedelta(seconds=resultado.atraso_segundos or 0)
    await repositorio.registrar_reagendamento(
        evento,
        total_tentativas=proxima_tentativa,
        proxima_tentativa_em=proxima_em,
        ultimo_status_http=resultado.status_http,
        ultimo_erro=resultado.erro,
    )
    logger.info(
        "Evento %s reagendado para %s (tentativa %d, atraso %ds): %s",
        evento.id_evento,
        proxima_em,
        proxima_tentativa,
        resultado.atraso_segundos,
        resultado.erro,
    )


async def processar_eventos_pendentes(
    fabrica_sessao: async_sessionmaker[AsyncSession],
    cliente_http: httpx.AsyncClient,
    agora: datetime,
    concorrencia_maxima: int,
    configuracao: Configuracao | None = None,
) -> None:
    configuracao_efetiva = configuracao or obter_configuracao()

    async with fabrica_sessao() as sessao:
        repositorio = RepositorioEventoWebhook(sessao)
        pendentes = await repositorio.listar_pendentes_elegiveis(agora, LIMITE_LOTE_WEBHOOK)
        await sessao.commit()

    semaforo = asyncio.Semaphore(concorrencia_maxima)
    enviador = EnviadorWebhook(cliente_http, configuracao_efetiva)

    async def processar(evento: EventoWebhook) -> None:
        async with semaforo, fabrica_sessao() as sessao_item:
            resultado = await sessao_item.execute(
                select(EventoWebhook)
                .options(selectinload(EventoWebhook.remessa))
                .where(EventoWebhook.id == evento.id)
            )
            evento_item = resultado.scalar_one_or_none()
            if evento_item is None:
                return
            await processar_evento(
                sessao_item,
                evento_item,
                enviador,
                agora,
            )
            await sessao_item.commit()

    resultados = await asyncio.gather(
        *(processar(evento) for evento in pendentes),
        return_exceptions=True,
    )
    for resultado in resultados:
        if isinstance(resultado, Exception):
            logger.error("Falha ao processar evento de webhook: %s", resultado)


async def laco_despachante_webhook(
    fabrica_sessao: async_sessionmaker[AsyncSession],
    cliente_http: httpx.AsyncClient,
    intervalo_segundos: float,
    concorrencia_maxima: int,
    configuracao: Configuracao | None = None,
) -> None:
    while True:
        try:
            await processar_eventos_pendentes(
                fabrica_sessao,
                cliente_http,
                datetime.now(UTC),
                concorrencia_maxima,
                configuracao,
            )
        except Exception:
            logger.exception("Erro na rotina de despachante de webhooks")

        await asyncio.sleep(intervalo_segundos)
