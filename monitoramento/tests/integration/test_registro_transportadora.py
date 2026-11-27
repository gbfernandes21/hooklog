import asyncio
import json
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.clients.cliente_transportadora import ClienteTransportadora
from app.core.configuracao import Configuracao, obter_configuracao
from app.core.dependencias import obter_cliente_transportadora
from app.main import app
from app.models.encomenda import Encomenda
from app.models.enums import StatusEncomenda
from app.models.historico_status import HistoricoStatus
from app.workers.registro_pendente import (
    laco_registro_pendente,
    processar_pendentes,
)

ADMIN_EMAIL = "admin@hooklog.test"
ADMIN_SENHA = "senha-admin-123"
AGORA = datetime(2026, 11, 29, 12, 0, 0, tzinfo=UTC)


async def _registrar_usuario(
    cliente: httpx.AsyncClient,
    email: str = "ana@exemplo.com",
    senha: str = "minhasenha123",
) -> int:
    resposta = await cliente.post(
        "/autenticacao/registro",
        json={"email": email, "senha": senha},
    )
    assert resposta.status_code == 201
    return resposta.json()["id"]


async def _fazer_login(
    cliente: httpx.AsyncClient,
    email: str = "ana@exemplo.com",
    senha: str = "minhasenha123",
) -> str:
    resposta = await cliente.post(
        "/autenticacao/login",
        data={"username": email, "password": senha},
    )
    assert resposta.status_code == 200
    return resposta.json()["access_token"]


async def _registrar_e_fazer_login(
    cliente: httpx.AsyncClient,
    email: str = "ana@exemplo.com",
    senha: str = "minhasenha123",
) -> str:
    await _registrar_usuario(cliente, email=email, senha=senha)
    return await _fazer_login(cliente, email=email, senha=senha)


async def _cadastrar(
    cliente: httpx.AsyncClient,
    token: str,
    codigo_rastreio: str = "BR123456789",
) -> httpx.Response:
    return await cliente.post(
        "/encomendas",
        json={
            "codigo_rastreio": codigo_rastreio,
            "descricao": "Fone de ouvido",
            "vendedor": "Loja Exemplo LTDA",
        },
        headers={"Authorization": f"Bearer {token}"},
    )


async def _criar_pendente(
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
    usuario_id: int,
    codigo_rastreio: str,
    agora: datetime,
    proxima_tentativa_em: datetime | None = None,
    tentativas_registro: int = 0,
) -> int:
    async with fabrica_sessao_teste() as sessao:
        encomenda = Encomenda(
            usuario_id=usuario_id,
            codigo_rastreio=codigo_rastreio,
            descricao="Fone de ouvido",
            vendedor="Loja Exemplo LTDA",
            status=StatusEncomenda.REGISTRO_PENDENTE.value,
            tentativas_registro=tentativas_registro,
            proxima_tentativa_em=(
                proxima_tentativa_em if proxima_tentativa_em is not None else agora
            ),
            criado_em=agora,
            atualizado_em=agora,
        )
        sessao.add(encomenda)
        await sessao.flush()
        sessao.add(
            HistoricoStatus(
                encomenda_id=encomenda.id,
                status_anterior=None,
                status_novo=StatusEncomenda.REGISTRO_PENDENTE.value,
                ocorrido_em=agora,
                registrado_em=agora,
            )
        )
        await sessao.commit()
        return encomenda.id


async def _obter_encomenda(
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
    encomenda_id: int,
) -> Encomenda:
    async with fabrica_sessao_teste() as sessao:
        resultado = await sessao.execute(select(Encomenda).where(Encomenda.id == encomenda_id))
        return resultado.scalar_one()


async def _contar_historico(
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
    encomenda_id: int,
) -> int:
    async with fabrica_sessao_teste() as sessao:
        resultado = await sessao.execute(
            select(func.count())
            .select_from(HistoricoStatus)
            .where(HistoricoStatus.encomenda_id == encomenda_id)
        )
        return resultado.scalar_one()


def _configuracao(**alteracoes: object) -> Configuracao:
    return obter_configuracao().model_copy(update=alteracoes)


@asynccontextmanager
async def _cliente_mock(handler) -> AsyncIterator[ClienteTransportadora]:
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as cliente_http:
        yield ClienteTransportadora(cliente_http, obter_configuracao())


@asynccontextmanager
async def _cliente_na_api(handler) -> AsyncIterator[ClienteTransportadora]:
    async with _cliente_mock(handler) as cliente_transportadora:
        anterior = app.dependency_overrides.get(obter_cliente_transportadora)
        app.dependency_overrides[obter_cliente_transportadora] = lambda: cliente_transportadora
        try:
            yield cliente_transportadora
        finally:
            if anterior is not None:
                app.dependency_overrides[obter_cliente_transportadora] = anterior
            else:
                app.dependency_overrides.pop(obter_cliente_transportadora, None)


# --- Cadastro de encomenda ---


async def test_cadastro_com_sucesso_fica_aguardando_envio_com_historico(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    token = await _registrar_e_fazer_login(cliente)
    capturado: dict = {}

    def responder(request: httpx.Request) -> httpx.Response:
        capturado["chave_api"] = request.headers.get("X-Chave-Api")
        capturado["corpo"] = json.loads(request.content)
        return httpx.Response(201)

    async with _cliente_na_api(responder):
        resposta = await _cadastrar(cliente, token)

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["status"] == "AGUARDANDO_ENVIO"
    assert corpo["grupo"] == "nao_encaminhadas"
    assert len(corpo["historico"]) == 2
    assert any(
        item["status_anterior"] == "REGISTRO_PENDENTE" and item["status_novo"] == "AGUARDANDO_ENVIO"
        for item in corpo["historico"]
    )
    assert capturado["chave_api"] == obter_configuracao().chave_api_transportadora
    assert capturado["corpo"] == {
        "codigo_rastreio": "BR123456789",
        "vendedor": "Loja Exemplo LTDA",
        "url_callback": obter_configuracao().url_publica_webhook,
    }

    encomenda = await _obter_encomenda(fabrica_sessao_teste, corpo["id"])
    assert encomenda.tentativas_registro == 0
    assert encomenda.proxima_tentativa_em is None
    assert encomenda.ultimo_erro_registro is None


@pytest.mark.parametrize("modo", ["timeout", "503"])
async def test_cadastro_com_falha_transitoria_fica_registro_pendente(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
    modo: str,
) -> None:
    token = await _registrar_e_fazer_login(cliente)

    def responder(request: httpx.Request) -> httpx.Response:
        if modo == "timeout":
            raise httpx.TimeoutException("Tempo esgotado", request=request)
        return httpx.Response(503)

    async with _cliente_na_api(responder):
        resposta = await _cadastrar(cliente, token)

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["status"] == "REGISTRO_PENDENTE"

    encomenda = await _obter_encomenda(fabrica_sessao_teste, corpo["id"])
    assert encomenda.tentativas_registro == 1
    assert encomenda.proxima_tentativa_em is not None
    assert encomenda.proxima_tentativa_em > datetime.now(UTC)
    assert encomenda.ultimo_erro_registro is not None


@pytest.mark.parametrize("status", [401, 422])
async def test_cadastro_com_erro_permanente_fica_falha_no_registro(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
    status: int,
) -> None:
    token = await _registrar_e_fazer_login(cliente)

    def responder(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status)

    async with _cliente_na_api(responder):
        resposta = await _cadastrar(cliente, token)

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["status"] == "FALHA_NO_REGISTRO"

    encomenda = await _obter_encomenda(fabrica_sessao_teste, corpo["id"])
    assert encomenda.proxima_tentativa_em is None
    assert encomenda.ultimo_erro_registro is not None


# --- POST /encomendas/{id}/registrar ---


async def test_registrar_volta_para_registro_pendente_com_tentativas_zeradas(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    token = await _registrar_e_fazer_login(cliente)

    def responder(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422)

    async with _cliente_na_api(responder):
        resposta = await _cadastrar(cliente, token)
    encomenda_id = resposta.json()["id"]
    assert resposta.json()["status"] == "FALHA_NO_REGISTRO"

    resposta = await cliente.post(
        f"/encomendas/{encomenda_id}/registrar",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resposta.status_code == 202
    corpo = resposta.json()
    assert corpo["status"] == "REGISTRO_PENDENTE"

    encomenda = await _obter_encomenda(fabrica_sessao_teste, encomenda_id)
    assert encomenda.tentativas_registro == 0
    assert encomenda.proxima_tentativa_em is not None
    assert encomenda.ultimo_erro_registro is None
    assert await _contar_historico(fabrica_sessao_teste, encomenda_id) == 3


async def test_registrar_em_estado_invalido_retorna_409(
    cliente: httpx.AsyncClient,
) -> None:
    token = await _registrar_e_fazer_login(cliente)
    resposta = await _cadastrar(cliente, token)
    assert resposta.json()["status"] == "REGISTRO_PENDENTE"
    encomenda_id = resposta.json()["id"]

    resposta = await cliente.post(
        f"/encomendas/{encomenda_id}/registrar",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resposta.status_code == 409
    assert resposta.json()["codigo"] == "ESTADO_INVALIDO"


async def test_registrar_encomenda_alheia_retorna_404(
    cliente: httpx.AsyncClient,
) -> None:
    token_a = await _registrar_e_fazer_login(cliente, email="ana@exemplo.com")

    def responder(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422)

    async with _cliente_na_api(responder):
        resposta = await _cadastrar(cliente, token_a)
    encomenda_id = resposta.json()["id"]

    token_b = await _registrar_e_fazer_login(cliente, email="bia@exemplo.com")
    resposta = await cliente.post(
        f"/encomendas/{encomenda_id}/registrar",
        headers={"Authorization": f"Bearer {token_b}"},
    )

    assert resposta.status_code == 404


async def test_registrar_com_admin_retorna_403(cliente: httpx.AsyncClient) -> None:
    token_admin = await _fazer_login(cliente, ADMIN_EMAIL, ADMIN_SENHA)

    resposta = await cliente.post(
        "/encomendas/1/registrar",
        headers={"Authorization": f"Bearer {token_admin}"},
    )

    assert resposta.status_code == 403


# --- Rotina de registro pendente ---


async def test_rotina_registra_pendente_vencida_e_ignora_nao_vencida(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    usuario_id = await _registrar_usuario(cliente)
    vencida_id = await _criar_pendente(
        fabrica_sessao_teste,
        usuario_id,
        "BR000000001",
        AGORA,
        proxima_tentativa_em=AGORA - timedelta(seconds=1),
    )
    futura_id = await _criar_pendente(
        fabrica_sessao_teste,
        usuario_id,
        "BR000000002",
        AGORA,
        proxima_tentativa_em=AGORA + timedelta(seconds=60),
    )
    chamadas: list[str] = []

    def responder(request: httpx.Request) -> httpx.Response:
        chamadas.append(json.loads(request.content)["codigo_rastreio"])
        return httpx.Response(201)

    async with _cliente_mock(responder) as cliente_transportadora:
        await processar_pendentes(
            fabrica_sessao_teste,
            cliente_transportadora,
            AGORA,
            5,
            _configuracao(),
        )

    vencida = await _obter_encomenda(fabrica_sessao_teste, vencida_id)
    futura = await _obter_encomenda(fabrica_sessao_teste, futura_id)
    assert vencida.status == "AGUARDANDO_ENVIO"
    assert futura.status == "REGISTRO_PENDENTE"
    assert chamadas == ["BR000000001"]


async def test_rotina_aplica_backoff_5_10_20_40_60_e_falha_ao_atingir_maximo(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    usuario_id = await _registrar_usuario(cliente)
    encomenda_id = await _criar_pendente(fabrica_sessao_teste, usuario_id, "BR000000001", AGORA)
    configuracao = _configuracao(
        max_tentativas_registro=6,
        base_backoff_registro_segundos=5,
        teto_backoff_registro_segundos=60,
    )

    def responder(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    async with _cliente_mock(responder) as cliente_transportadora:
        agora = AGORA
        for numero, atraso_esperado in enumerate([5, 10, 20, 40, 60], start=1):
            await processar_pendentes(
                fabrica_sessao_teste,
                cliente_transportadora,
                agora,
                5,
                configuracao,
            )
            encomenda = await _obter_encomenda(fabrica_sessao_teste, encomenda_id)
            assert encomenda.tentativas_registro == numero
            assert encomenda.proxima_tentativa_em is not None
            assert (encomenda.proxima_tentativa_em - agora).total_seconds() == atraso_esperado
            agora = encomenda.proxima_tentativa_em

        await processar_pendentes(
            fabrica_sessao_teste,
            cliente_transportadora,
            agora,
            5,
            configuracao,
        )

    encomenda = await _obter_encomenda(fabrica_sessao_teste, encomenda_id)
    assert encomenda.tentativas_registro == 6
    assert encomenda.status == "FALHA_NO_REGISTRO"
    assert encomenda.proxima_tentativa_em is None


async def test_rotina_erro_permanente_vira_falha_no_registro_na_hora(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    usuario_id = await _registrar_usuario(cliente)
    encomenda_id = await _criar_pendente(fabrica_sessao_teste, usuario_id, "BR000000001", AGORA)

    def responder(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422)

    async with _cliente_mock(responder) as cliente_transportadora:
        await processar_pendentes(
            fabrica_sessao_teste,
            cliente_transportadora,
            AGORA,
            5,
            _configuracao(),
        )

    encomenda = await _obter_encomenda(fabrica_sessao_teste, encomenda_id)
    assert encomenda.status == "FALHA_NO_REGISTRO"
    assert encomenda.proxima_tentativa_em is None
    assert encomenda.ultimo_erro_registro is not None


async def test_rotina_processa_lote_em_paralelo_respeitando_concorrencia(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    usuario_id = await _registrar_usuario(cliente)
    ids = [
        await _criar_pendente(fabrica_sessao_teste, usuario_id, f"BR{i:09d}", AGORA)
        for i in range(10)
    ]
    ativos = 0
    max_ativos = 0

    async def responder(request: httpx.Request) -> httpx.Response:
        nonlocal ativos, max_ativos
        ativos += 1
        max_ativos = max(max_ativos, ativos)
        try:
            await asyncio.sleep(0.2)
            return httpx.Response(201)
        finally:
            ativos -= 1

    async with _cliente_mock(responder) as cliente_transportadora:
        inicio = time.monotonic()
        await processar_pendentes(
            fabrica_sessao_teste,
            cliente_transportadora,
            AGORA,
            5,
            _configuracao(),
        )
        duracao = time.monotonic() - inicio

    assert duracao < 2.0
    assert max_ativos <= 5
    for encomenda_id in ids:
        encomenda = await _obter_encomenda(fabrica_sessao_teste, encomenda_id)
        assert encomenda.status == "AGUARDANDO_ENVIO"


async def test_laco_sobrevive_a_excecao_e_termina_ao_ser_cancelado() -> None:
    class FabricaQueFalha:
        def __init__(self) -> None:
            self.chamadas = 0

        def __call__(self):
            self.chamadas += 1
            raise RuntimeError("falha simulada")

    def responder(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201)

    fabrica = FabricaQueFalha()
    async with _cliente_mock(responder) as cliente_transportadora:
        tarefa = asyncio.create_task(laco_registro_pendente(fabrica, cliente_transportadora, 0, 5))
        for _ in range(5):
            await asyncio.sleep(0)

        assert fabrica.chamadas >= 1
        assert not tarefa.done()

        tarefa.cancel()
        with pytest.raises(asyncio.CancelledError):
            await tarefa

    assert tarefa.cancelled()
