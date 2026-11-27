import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.clients.cliente_transportadora import ClienteTransportadora
from app.core.configuracao import Configuracao, obter_configuracao
from app.services.servico_encomenda import ServicoEncomenda

logger = logging.getLogger(__name__)

LIMITE_LOTE_REGISTRO = 20


async def processar_pendentes(
    fabrica_sessao: async_sessionmaker[AsyncSession],
    cliente: ClienteTransportadora,
    agora: datetime,
    concorrencia_maxima: int,
    configuracao: Configuracao | None = None,
) -> None:
    configuracao_efetiva = configuracao or obter_configuracao()

    async with fabrica_sessao() as sessao:
        servico = ServicoEncomenda(sessao)
        pendentes = await servico.listar_pendentes_para_registro(agora, LIMITE_LOTE_REGISTRO)
        ids = [encomenda.id for encomenda in pendentes]
        await sessao.commit()

    semaforo = asyncio.Semaphore(concorrencia_maxima)

    async def registrar(encomenda_id: int) -> None:
        async with semaforo, fabrica_sessao() as sessao_item:
            servico_item = ServicoEncomenda(sessao_item)
            encomenda = await servico_item.obter_pendente_para_registro(encomenda_id, agora)
            if encomenda is None:
                return
            await servico_item.registrar_na_transportadora(
                encomenda,
                cliente,
                agora,
                configuracao_efetiva,
            )

    resultados = await asyncio.gather(
        *(registrar(encomenda_id) for encomenda_id in ids),
        return_exceptions=True,
    )
    for resultado in resultados:
        if isinstance(resultado, Exception):
            logger.error("Falha ao processar registro pendente: %s", resultado)


async def laco_registro_pendente(
    fabrica_sessao: async_sessionmaker[AsyncSession],
    cliente: ClienteTransportadora,
    intervalo_segundos: float,
    concorrencia_maxima: int,
    configuracao: Configuracao | None = None,
) -> None:
    configuracao_efetiva = configuracao or obter_configuracao()

    while True:
        try:
            await processar_pendentes(
                fabrica_sessao,
                cliente,
                datetime.now(UTC),
                concorrencia_maxima,
                configuracao_efetiva,
            )
        except Exception:
            logger.exception("Erro na rotina de registro pendente")

        await asyncio.sleep(intervalo_segundos)
