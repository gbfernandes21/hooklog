import asyncio
import time
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.configuracao import obter_configuracao
from app.models.enums import EstadoEnvio, StatusRemessa
from app.models.evento_webhook import EventoWebhook
from app.models.remessa import Remessa
from app.models.tentativa_webhook import TentativaWebhook
from app.workers.despachante_webhook import processar_eventos_pendentes

AGORA = datetime(2026, 11, 30, 12, 0, 0, tzinfo=UTC)
URL_CALLBACK = "http://monitoramento:8000/webhooks/transportadora"
CORPO_BASE = (
    '{{"id_evento": "{id_evento}", '
    '"tipo_evento": "remessa.status_alterado", '
    '"codigo_rastreio": "{codigo}", '
    '"status": "POSTADO", '
    '"vendedor": "Loja Exemplo LTDA", '
    '"ocorrido_em": "2026-11-30T12:00:00Z"}}'
)


def _corpo(id_evento: str, codigo: str) -> str:
    return CORPO_BASE.format(id_evento=id_evento, codigo=codigo)


async def _criar_remessa(
    sessao: AsyncSession,
    codigo: str,
    status: str = StatusRemessa.POSTADO.value,
) -> Remessa:
    remessa = Remessa(
        codigo_rastreio=codigo,
        vendedor="Loja Exemplo LTDA",
        status=status,
        url_callback=URL_CALLBACK,
        criado_em=AGORA,
        atualizado_em=AGORA,
    )
    sessao.add(remessa)
    await sessao.flush()
    return remessa


async def _criar_evento(
    sessao: AsyncSession,
    remessa: Remessa,
    id_evento: str,
    estado: str = EstadoEnvio.PENDENTE.value,
    total_tentativas: int = 0,
    proxima_tentativa_em: datetime | None = None,
) -> EventoWebhook:
    evento = EventoWebhook(
        remessa_id=remessa.id,
        id_evento=id_evento,
        tipo_evento="remessa.status_alterado",
        corpo=_corpo(id_evento, remessa.codigo_rastreio),
        estado=estado,
        total_tentativas=total_tentativas,
        proxima_tentativa_em=proxima_tentativa_em or AGORA,
        criado_em=AGORA,
    )
    sessao.add(evento)
    await sessao.flush()
    return evento


async def _obter_evento(
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
    id_evento: str,
) -> EventoWebhook | None:
    async with fabrica_sessao_teste() as sessao:
        resultado = await sessao.execute(
            select(EventoWebhook).where(EventoWebhook.id_evento == id_evento)
        )
        return resultado.scalar_one_or_none()


async def _contar_tentativas(
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> int:
    async with fabrica_sessao_teste() as sessao:
        resultado = await sessao.execute(select(func.count()).select_from(TentativaWebhook))
        return resultado.scalar_one()


async def _listar_tentativas_evento(
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
    id_evento: str,
) -> list[TentativaWebhook]:
    async with fabrica_sessao_teste() as sessao:
        resultado = await sessao.execute(
            select(TentativaWebhook)
            .join(EventoWebhook)
            .where(EventoWebhook.id_evento == id_evento)
            .order_by(TentativaWebhook.numero)
        )
        return list(resultado.scalars().all())


class _DestinoSimulado:
    def __init__(self) -> None:
        self.corpos_enviados: list[bytes] = []
        self.carimbos: list[str] = []
        self.status_por_chave: dict[str, int] = {}
        self.delay_segundos: float = 0.0
        self.chamadas_concorrentes = 0
        self.max_concorrentes = 0
        self.ativa = True

    async def handler(self, request: httpx.Request) -> httpx.Response:
        self.chamadas_concorrentes += 1
        self.max_concorrentes = max(self.max_concorrentes, self.chamadas_concorrentes)
        try:
            self.corpos_enviados.append(request.content)
            self.carimbos.append(request.headers.get("X-Carimbo-Tempo", ""))
            if self.delay_segundos:
                await asyncio.sleep(self.delay_segundos)
            codigo = request.headers.get("X-Status-Codigo", "200")
            return httpx.Response(int(codigo), content=b"ok")
        finally:
            self.chamadas_concorrentes -= 1


@pytest.fixture
def destino() -> _DestinoSimulado:
    return _DestinoSimulado()


@pytest.fixture
def cliente_mock(destino: _DestinoSimulado) -> httpx.AsyncClient:
    transporte = httpx.MockTransport(destino.handler)
    return httpx.AsyncClient(transport=transporte)


# --- Sucesso ---


async def test_200_marca_evento_enviado_com_enviado_em(
    cliente: httpx.AsyncClient,
    cliente_mock: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
    destino: _DestinoSimulado,
) -> None:
    async with fabrica_sessao_teste() as sessao:
        remessa = await _criar_remessa(sessao, "BR111111111")
        await _criar_evento(sessao, remessa, "evt-um")
        await sessao.commit()

    await processar_eventos_pendentes(
        fabrica_sessao_teste,
        cliente_mock,
        AGORA,
        concorrencia_maxima=5,
    )

    evento_atualizado = await _obter_evento(fabrica_sessao_teste, "evt-um")
    assert evento_atualizado is not None
    assert evento_atualizado.estado == EstadoEnvio.ENVIADO.value
    assert evento_atualizado.enviado_em is not None
    assert evento_atualizado.total_tentativas == 1
    assert evento_atualizado.ultimo_status_http == 200
    assert evento_atualizado.ultimo_erro is None


async def test_200_apos_retry_atualiza_total_tentativas_e_ultimo_status_http(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    chamadas = {"n": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        chamadas["n"] += 1
        if chamadas["n"] == 1:
            return httpx.Response(500)
        return httpx.Response(200)

    cliente_mock = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    async with fabrica_sessao_teste() as sessao:
        remessa = await _criar_remessa(sessao, "BR121212121")
        await _criar_evento(sessao, remessa, "evt-sucesso-apos-retry")
        await sessao.commit()

    configuracao = obter_configuracao()
    await processar_eventos_pendentes(
        fabrica_sessao_teste,
        cliente_mock,
        AGORA,
        concorrencia_maxima=5,
        configuracao=configuracao,
    )

    evento_apos_falha = await _obter_evento(fabrica_sessao_teste, "evt-sucesso-apos-retry")
    assert evento_apos_falha is not None
    assert evento_apos_falha.estado == EstadoEnvio.PENDENTE.value
    assert evento_apos_falha.total_tentativas == 1
    assert evento_apos_falha.ultimo_status_http == 500

    await processar_eventos_pendentes(
        fabrica_sessao_teste,
        cliente_mock,
        evento_apos_falha.proxima_tentativa_em,
        concorrencia_maxima=5,
        configuracao=configuracao,
    )

    evento_atualizado = await _obter_evento(fabrica_sessao_teste, "evt-sucesso-apos-retry")
    assert evento_atualizado is not None
    assert evento_atualizado.estado == EstadoEnvio.ENVIADO.value
    assert evento_atualizado.total_tentativas == 2
    assert evento_atualizado.ultimo_status_http == 200
    assert evento_atualizado.ultimo_erro is None
    assert evento_atualizado.enviado_em is not None

    tentativas = await _listar_tentativas_evento(fabrica_sessao_teste, "evt-sucesso-apos-retry")
    assert [tentativa.numero for tentativa in tentativas] == [1, 2]
    assert [tentativa.status_http for tentativa in tentativas] == [500, 200]


async def test_corpo_enviado_é_byte_a_byte_igual_ao_guardado(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
    destino: _DestinoSimulado,
) -> None:
    async with fabrica_sessao_teste() as sessao:
        remessa = await _criar_remessa(sessao, "BR222222222")
        evento = await _criar_evento(sessao, remessa, "evt-corpo")
        corpo_esperado = evento.corpo.encode("utf-8")
        await sessao.commit()

    cliente_mock = httpx.AsyncClient(transport=httpx.MockTransport(destino.handler))
    await processar_eventos_pendentes(
        fabrica_sessao_teste,
        cliente_mock,
        AGORA,
        concorrencia_maxima=5,
    )

    assert len(destino.corpos_enviados) == 1
    assert destino.corpos_enviados[0] == corpo_esperado


async def test_assinatura_contem_prefixo_sha256_e_carimbo_injetado(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
    destino: _DestinoSimulado,
) -> None:
    async with fabrica_sessao_teste() as sessao:
        remessa = await _criar_remessa(sessao, "BR333333333")
        await _criar_evento(sessao, remessa, "evt-assinatura")
        await sessao.commit()

    cliente_mock = httpx.AsyncClient(transport=httpx.MockTransport(destino.handler))
    await processar_eventos_pendentes(
        fabrica_sessao_teste,
        cliente_mock,
        AGORA,
        concorrencia_maxima=5,
    )

    assert len(destino.carimbos) == 1
    assert destino.carimbos[0] == str(int(AGORA.timestamp()))
    assert destino.corpos_enviados[0] is not None


# --- Retry com backoff (500, timeout, conexão recusada) ---


async def test_500_reagenda_com_atrasos_1_2_4_8_e_falha_na_quinta(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    chamadas = {"n": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        chamadas["n"] += 1
        return httpx.Response(500)

    cliente_mock = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    async with fabrica_sessao_teste() as sessao:
        remessa = await _criar_remessa(sessao, "BR444444444")
        await _criar_evento(sessao, remessa, "evt-retry")
        await sessao.commit()

    configuracao = obter_configuracao()
    # Cada execução do despachante usa um "agora" avançado, de modo que o
    # proxima_tentativa_em (com backoff 1, 2, 4, 8) fique vencido na próxima.
    agora_atual = AGORA
    for _ in range(5):
        await processar_eventos_pendentes(
            fabrica_sessao_teste,
            cliente_mock,
            agora_atual,
            concorrencia_maxima=5,
            configuracao=configuracao,
        )
        evento_intermediario = await _obter_evento(fabrica_sessao_teste, "evt-retry")
        assert evento_intermediario is not None
        proxima = evento_intermediario.proxima_tentativa_em
        if evento_intermediario.estado == EstadoEnvio.PENDENTE.value and proxima is not None:
            agora_atual = proxima + timedelta(seconds=1)

    assert chamadas["n"] == 5
    evento_atualizado = await _obter_evento(fabrica_sessao_teste, "evt-retry")
    assert evento_atualizado is not None
    assert evento_atualizado.estado == EstadoEnvio.FALHA.value
    assert evento_atualizado.total_tentativas == 5

    tentativas = await _listar_tentativas_evento(fabrica_sessao_teste, "evt-retry")
    assert len(tentativas) == 5
    for tentativa in tentativas:
        assert tentativa.status_http == 500


async def test_timeout_e_conexao_recusada_reagem_com_retry(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    async def handler_timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout")

    async def handler_recusada(request: httpx.Request) -> httpx.Response:
        raise httpx.TransportError("conexao recusada")

    cliente_timeout = httpx.AsyncClient(transport=httpx.MockTransport(handler_timeout))
    cliente_recusada = httpx.AsyncClient(transport=httpx.MockTransport(handler_recusada))

    configuracao = obter_configuracao()

    async with fabrica_sessao_teste() as sessao:
        remessa = await _criar_remessa(sessao, "BR555555555")
        await _criar_evento(sessao, remessa, "evt-timeout")
        await _criar_remessa(sessao, "BR666666666")
        await _criar_evento(sessao, remessa, "evt-recusada")
        await sessao.commit()

    await processar_eventos_pendentes(
        fabrica_sessao_teste,
        cliente_timeout,
        AGORA,
        concorrencia_maxima=5,
        configuracao=configuracao,
    )
    await processar_eventos_pendentes(
        fabrica_sessao_teste,
        cliente_recusada,
        AGORA,
        concorrencia_maxima=5,
        configuracao=configuracao,
    )

    evt_t = await _obter_evento(fabrica_sessao_teste, "evt-timeout")
    evt_r = await _obter_evento(fabrica_sessao_teste, "evt-recusada")
    assert evt_t is not None and evt_t.estado == EstadoEnvio.PENDENTE.value
    assert evt_r is not None and evt_r.estado == EstadoEnvio.PENDENTE.value
    assert evt_t.proxima_tentativa_em is not None
    assert evt_r.proxima_tentativa_em is not None


# --- Falha permanente na primeira tentativa (401, 404, 409, 422) ---


@pytest.mark.parametrize("status", [401, 404, 409, 422])
async def test_4xx_permanente_marca_falha_na_primeira_tentativa_sem_retry(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
    status: int,
) -> None:
    chamadas = {"n": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        chamadas["n"] += 1
        return httpx.Response(status)

    cliente_mock = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    async with fabrica_sessao_teste() as sessao:
        remessa = await _criar_remessa(sessao, "BR777777777")
        await _criar_evento(sessao, remessa, "evt-permanente")
        await sessao.commit()

    await processar_eventos_pendentes(
        fabrica_sessao_teste,
        cliente_mock,
        AGORA,
        concorrencia_maxima=5,
    )

    assert chamadas["n"] == 1
    evento_atualizado = await _obter_evento(fabrica_sessao_teste, "evt-permanente")
    assert evento_atualizado is not None
    assert evento_atualizado.estado == EstadoEnvio.FALHA.value
    assert evento_atualizado.total_tentativas == 1


@pytest.mark.parametrize("status", [408, 429])
async def test_408_429_fazem_retry(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
    status: int,
) -> None:
    chamadas = {"n": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        chamadas["n"] += 1
        return httpx.Response(status)

    cliente_mock = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    async with fabrica_sessao_teste() as sessao:
        remessa = await _criar_remessa(sessao, "BR888888888")
        await _criar_evento(sessao, remessa, "evt-temporario")
        await sessao.commit()

    configuracao = obter_configuracao()
    await processar_eventos_pendentes(
        fabrica_sessao_teste,
        cliente_mock,
        AGORA,
        concorrencia_maxima=5,
        configuracao=configuracao,
    )

    assert chamadas["n"] == 1
    evento_atualizado = await _obter_evento(fabrica_sessao_teste, "evt-temporario")
    assert evento_atualizado is not None
    assert evento_atualizado.estado == EstadoEnvio.PENDENTE.value
    assert evento_atualizado.total_tentativas == 1
    assert evento_atualizado.proxima_tentativa_em is not None


# --- Ordem por remessa ---


async def test_evento_mais_novo_espera_mais_antigo_da_mesma_remessa(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    processados = {"n": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        processados["n"] += 1
        return httpx.Response(200)

    cliente_mock = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    async with fabrica_sessao_teste() as sessao:
        remessa = await _criar_remessa(sessao, "BR999999999")
        await _criar_evento(sessao, remessa, "evt-antigo", proxima_tentativa_em=AGORA)
        await _criar_evento(sessao, remessa, "evt-novo", proxima_tentativa_em=AGORA)
        await sessao.commit()

    await processar_eventos_pendentes(
        fabrica_sessao_teste,
        cliente_mock,
        AGORA,
        concorrencia_maxima=5,
    )

    assert processados["n"] == 1
    antigo = await _obter_evento(fabrica_sessao_teste, "evt-antigo")
    novo = await _obter_evento(fabrica_sessao_teste, "evt-novo")
    assert antigo is not None and antigo.estado == EstadoEnvio.ENVIADO.value
    assert novo is not None and novo.estado == EstadoEnvio.PENDENTE.value
    assert novo.total_tentativas == 0


async def test_remessas_diferivas_nao_se_bloqueiam(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    processados = {"n": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        processados["n"] += 1
        return httpx.Response(200)

    cliente_mock = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    async with fabrica_sessao_teste() as sessao:
        remessa_a = await _criar_remessa(sessao, "BR000000001")
        remessa_b = await _criar_remessa(sessao, "BR000000002")
        await _criar_evento(sessao, remessa_a, "evt-a", proxima_tentativa_em=AGORA)
        await _criar_evento(sessao, remessa_b, "evt-b", proxima_tentativa_em=AGORA)
        await sessao.commit()

    await processar_eventos_pendentes(
        fabrica_sessao_teste,
        cliente_mock,
        AGORA,
        concorrencia_maxima=5,
    )

    assert processados["n"] == 2
    a = await _obter_evento(fabrica_sessao_teste, "evt-a")
    b = await _obter_evento(fabrica_sessao_teste, "evt-b")
    assert a is not None and a.estado == EstadoEnvio.ENVIADO.value
    assert b is not None and b.estado == EstadoEnvio.ENVIADO.value


# --- Paralelismo ---


async def test_dez_eventos_remessas_diferivas_enviados_em_menos_que_2s(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
    destino: _DestinoSimulado,
) -> None:
    destino.delay_segundos = 0.2

    async with fabrica_sessao_teste() as sessao:
        for i in range(10):
            remessa = await _criar_remessa(sessao, f"BRP{i:07d}")
            await _criar_evento(sessao, remessa, f"evt-par-{i}", proxima_tentativa_em=AGORA)
        await sessao.commit()

    cliente_mock = httpx.AsyncClient(transport=httpx.MockTransport(destino.handler))
    inicio = time.monotonic()
    await processar_eventos_pendentes(
        fabrica_sessao_teste,
        cliente_mock,
        AGORA,
        concorrencia_maxima=5,
    )
    duracao = time.monotonic() - inicio

    assert destino.chamadas_concorrentes == 0
    assert destino.max_concorrentes <= 5
    assert len(destino.corpos_enviados) == 10
    assert duracao < 2.0
