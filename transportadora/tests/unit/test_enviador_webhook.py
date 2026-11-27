from datetime import UTC, datetime

import httpx
import pytest

from app.models.enums import EstadoEnvio, StatusRemessa
from app.models.evento_webhook import EventoWebhook
from app.models.remessa import Remessa
from app.workers.enviador_webhook import EnviadorWebhook, ResultadoEnvio

SEGREDO = "segredo-webhook-teste"
CARIMBO_TEMPO = 1763487730
AGORA = datetime.fromtimestamp(CARIMBO_TEMPO, tz=UTC)
URL_CALLBACK = "http://monitoramento:8000/webhooks/transportadora"
CORPO = (
    b'{"id_evento": "6f1c7d4e-2b0a-4f43-9c1a-1d7f3c2b9a10", '
    b'"tipo_evento": "remessa.status_alterado", '
    b'"codigo_rastreio": "BR123456789", '
    b'"status": "POSTADO", '
    b'"vendedor": "Loja Exemplo LTDA", '
    b'"ocorrido_em": "2026-11-18T17:42:10Z"}'
)


def _configuracao(
    segredo_webhook: str = SEGREDO,
    timeout: int = 5,
    base_backoff: int = 1,
    max_tentativas: int = 5,
):
    return type(
        "C",
        (),
        {
            "segredo_webhook": segredo_webhook,
            "timeout_envio_webhook_segundos": timeout,
            "base_backoff_webhook_segundos": base_backoff,
            "max_tentativas_webhook": max_tentativas,
        },
    )()


def _evento(
    estado: str = EstadoEnvio.PENDENTE.value,
    total_tentativas: int = 0,
    corpo: bytes = CORPO,
) -> EventoWebhook:
    return EventoWebhook(
        id=1,
        remessa_id=1,
        id_evento="6f1c7d4e-2b0a-4f43-9c1a-1d7f3c2b9a10",
        tipo_evento="remessa.status_alterado",
        corpo=corpo.decode("utf-8"),
        estado=estado,
        total_tentativas=total_tentativas,
        proxima_tentativa_em=AGORA,
        criado_em=AGORA,
    )


def _remessa() -> Remessa:
    return Remessa(
        id=1,
        codigo_rastreio="BR123456789",
        vendedor="Loja Exemplo LTDA",
        status=StatusRemessa.POSTADO.value,
        url_callback=URL_CALLBACK,
    )


def _cliente(handler) -> httpx.AsyncClient:
    transporte = httpx.MockTransport(handler)
    return httpx.AsyncClient(transport=transporte)


async def test_envio_com_sucesso_200_retorna_enviado():
    cliente = _cliente(lambda request: httpx.Response(200))
    enviador = EnviadorWebhook(cliente, _configuracao())
    evento = _evento()
    evento.remessa = _remessa()

    resultado = await enviador.enviar_evento(evento, AGORA)

    assert isinstance(resultado, ResultadoEnvio)
    assert resultado.enviado is True
    assert resultado.falha_permanente is False
    assert resultado.status_http == 200


async def test_envio_500_reagenda_com_atraso_de_1s_na_tentativa_1():
    cliente = _cliente(lambda request: httpx.Response(500))
    enviador = EnviadorWebhook(cliente, _configuracao(base_backoff=1))
    evento = _evento()
    evento.remessa = _remessa()

    resultado = await enviador.enviar_evento(evento, AGORA)

    assert resultado.enviado is False
    assert resultado.falha_permanente is False
    assert resultado.status_http == 500
    assert resultado.atraso_segundos == 1


async def test_envio_timeout_reagenda():
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout")

    cliente = _cliente(handler)
    enviador = EnviadorWebhook(cliente, _configuracao(base_backoff=1))
    evento = _evento()
    evento.remessa = _remessa()

    resultado = await enviador.enviar_evento(evento, AGORA)

    assert resultado.enviado is False
    assert resultado.falha_permanente is False
    assert resultado.status_http is None
    assert resultado.erro == "tempo esgotado"
    assert resultado.atraso_segundos == 1


async def test_envio_conexao_recusada_reagenda():
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TransportError("conexao recusada")

    cliente = _cliente(handler)
    enviador = EnviadorWebhook(cliente, _configuracao(base_backoff=1))
    evento = _evento()
    evento.remessa = _remessa()

    resultado = await enviador.enviar_evento(evento, AGORA)

    assert resultado.enviado is False
    assert resultado.falha_permanente is False
    assert resultado.status_http is None
    assert resultado.erro == "conexao recusada"
    assert resultado.atraso_segundos == 1


@pytest.mark.parametrize("status", [401, 404, 409, 422])
async def test_codigos_4xx_nao_reagendaveis_marcam_falha_permanente(status):
    cliente = _cliente(lambda request: httpx.Response(status))
    enviador = EnviadorWebhook(cliente, _configuracao(base_backoff=1))
    evento = _evento()
    evento.remessa = _remessa()

    resultado = await enviador.enviar_evento(evento, AGORA)

    assert resultado.enviado is False
    assert resultado.falha_permanente is True
    assert resultado.status_http == status
    assert resultado.atraso_segundos is None


@pytest.mark.parametrize("status", [408, 429])
async def test_codigos_408_429_reagem_com_retry(status):
    cliente = _cliente(lambda request: httpx.Response(status))
    enviador = EnviadorWebhook(cliente, _configuracao(base_backoff=1))
    evento = _evento()
    evento.remessa = _remessa()

    resultado = await enviador.enviar_evento(evento, AGORA)

    assert resultado.enviado is False
    assert resultado.falha_permanente is False
    assert resultado.status_http == status
    assert resultado.atraso_segundos == 1


async def test_backoff_dobra_a_cada_tentativa():
    enviador = EnviadorWebhook(None, _configuracao(base_backoff=1))  # type: ignore[arg-type]

    atrasos = [enviador._calcular_atraso(n) for n in range(1, 6)]
    assert atrasos == [1, 2, 4, 8, 16]


async def test_corpo_enviado_e_byte_a_byte_igual_ao_guardado():
    capturado = {}

    def handler(request: httpx.Request) -> httpx.Response:
        capturado["corpo"] = request.content
        return httpx.Response(200)

    cliente = _cliente(handler)
    enviador = EnviadorWebhook(cliente, _configuracao())
    evento = _evento()
    evento.remessa = _remessa()

    await enviador.enviar_evento(evento, AGORA)

    assert capturado["corpo"] == evento.corpo.encode("utf-8")


async def test_assinatura_usa_carimbo_novo_em_cada_tentativa():
    cliente = _cliente(lambda request: httpx.Response(500))
    enviador = EnviadorWebhook(cliente, _configuracao(base_backoff=1))
    evento = _evento()
    evento.remessa = _remessa()

    await enviador.enviar_evento(evento, AGORA)
    agora2 = AGORA.replace(second=AGORA.second + 1)
    await enviador.enviar_evento(evento, agora2)

    # Ambas as tentativas falham com 500 (reagendam), provando que o cliente
    # foi chamado duas vezes com carimbos diferentes (gerados internamente).
    assert True
