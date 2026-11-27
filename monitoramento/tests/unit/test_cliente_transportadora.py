import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace

import httpx
import pytest

from app.clients.cliente_transportadora import (
    ClienteTransportadora,
    ErroPermanente,
    ErroTransitorio,
)

CHAVE_API = "chave-api-teste"
URL_BASE = "http://transportadora:8001"


def _configuracao() -> SimpleNamespace:
    return SimpleNamespace(
        url_transportadora=URL_BASE,
        chave_api_transportadora=CHAVE_API,
    )


@asynccontextmanager
async def _cliente_com(handler) -> AsyncIterator[ClienteTransportadora]:
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as cliente_http:
        yield ClienteTransportadora(cliente_http, _configuracao())


async def _registrar(cliente: ClienteTransportadora) -> None:
    await cliente.registrar_remessa(
        codigo_rastreio="BR123456789",
        vendedor="Loja Exemplo LTDA",
        url_callback="http://monitoramento:8000/webhooks/transportadora",
    )


async def test_registrar_remessa_envia_corpo_e_chave_api() -> None:
    capturado: dict = {}

    def responder(request: httpx.Request) -> httpx.Response:
        capturado["url"] = str(request.url)
        capturado["chave_api"] = request.headers.get("X-Chave-Api")
        capturado["corpo"] = json.loads(request.content)
        return httpx.Response(201)

    async with _cliente_com(responder) as cliente:
        await _registrar(cliente)

    assert capturado["url"] == f"{URL_BASE}/remessas"
    assert capturado["chave_api"] == CHAVE_API
    assert capturado["corpo"] == {
        "codigo_rastreio": "BR123456789",
        "vendedor": "Loja Exemplo LTDA",
        "url_callback": "http://monitoramento:8000/webhooks/transportadora",
    }


@pytest.mark.parametrize("status", [200, 201])
async def test_registrar_remessa_aceita_sucesso(status: int) -> None:
    def responder(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status)

    async with _cliente_com(responder) as cliente:
        await _registrar(cliente)


@pytest.mark.parametrize("status", [408, 429, 500, 503])
async def test_registrar_remessa_resposta_transitoria_levanta_erro_transitorio(
    status: int,
) -> None:
    def responder(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status)

    async with _cliente_com(responder) as cliente:
        with pytest.raises(ErroTransitorio):
            await _registrar(cliente)


@pytest.mark.parametrize("status", [401, 403, 422])
async def test_registrar_remessa_resposta_permanente_levanta_erro_permanente(
    status: int,
) -> None:
    def responder(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status)

    async with _cliente_com(responder) as cliente:
        with pytest.raises(ErroPermanente):
            await _registrar(cliente)


async def test_registrar_remessa_timeout_levanta_erro_transitorio() -> None:
    def responder(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("Tempo esgotado", request=request)

    async with _cliente_com(responder) as cliente:
        with pytest.raises(ErroTransitorio):
            await _registrar(cliente)


async def test_registrar_remessa_conexao_recusada_levanta_erro_transitorio() -> None:
    def responder(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Conexão recusada", request=request)

    async with _cliente_com(responder) as cliente:
        with pytest.raises(ErroTransitorio):
            await _registrar(cliente)
