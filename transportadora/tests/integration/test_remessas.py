import asyncio
import json
import uuid

import httpx
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.configuracao import obter_configuracao
from app.main import app
from app.models.enums import EstadoEnvio, StatusRemessa
from app.models.evento_webhook import EventoWebhook
from app.models.remessa import Remessa
from app.models.tentativa_webhook import TentativaWebhook

ADMIN_EMAIL = "admin@hooklog.test"
ADMIN_SENHA = "senha-admin-123"
URL_CALLBACK = "http://monitoramento:8000/webhooks/transportadora"
CODIGO = "BR123456789"
SEQUENCIA = ["POSTADO", "EM_TRANSITO", "SAIU_PARA_ENTREGA"]


async def _login_admin(cliente: httpx.AsyncClient) -> str:
    resposta = await cliente.post(
        "/autenticacao/login",
        data={"username": ADMIN_EMAIL, "password": ADMIN_SENHA},
    )
    assert resposta.status_code == 200
    return resposta.json()["access_token"]


def _cabecalho_admin(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _cabecalho_chave() -> dict[str, str]:
    return {"X-Chave-Api": obter_configuracao().chave_api_servico}


async def _criar_remessa(
    cliente: httpx.AsyncClient,
    codigo_rastreio: str = CODIGO,
    vendedor: str = "Loja Exemplo LTDA",
    url_callback: str = URL_CALLBACK,
) -> httpx.Response:
    return await cliente.post(
        "/remessas",
        json={
            "codigo_rastreio": codigo_rastreio,
            "vendedor": vendedor,
            "url_callback": url_callback,
        },
        headers=_cabecalho_chave(),
    )


async def _mudar_status(
    cliente: httpx.AsyncClient,
    token: str,
    codigo_rastreio: str,
    status: str,
) -> httpx.Response:
    return await cliente.post(
        f"/remessas/{codigo_rastreio}/status",
        json={"status": status},
        headers=_cabecalho_admin(token),
    )


async def _entregar(
    cliente: httpx.AsyncClient,
    token: str,
    codigo_rastreio: str,
    recebido_por: str | None = None,
) -> httpx.Response:
    corpo = {} if recebido_por is None else {"recebido_por": recebido_por}
    return await cliente.post(
        f"/remessas/{codigo_rastreio}/entregar",
        json=corpo,
        headers=_cabecalho_admin(token),
    )


async def _avancar_ate(
    cliente: httpx.AsyncClient,
    token: str,
    codigo_rastreio: str,
    status_alvo: str,
) -> None:
    for status in SEQUENCIA:
        resposta = await _mudar_status(cliente, token, codigo_rastreio, status)
        assert resposta.status_code == 200
        if status == status_alvo:
            return
    raise AssertionError(f"status alvo inválido: {status_alvo}")


async def _obter_remessa(
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
    codigo_rastreio: str,
) -> Remessa | None:
    async with fabrica_sessao_teste() as sessao:
        resultado = await sessao.execute(
            select(Remessa).where(Remessa.codigo_rastreio == codigo_rastreio)
        )
        return resultado.scalar_one_or_none()


async def _contar_remessas(
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> int:
    async with fabrica_sessao_teste() as sessao:
        resultado = await sessao.execute(select(func.count()).select_from(Remessa))
        return resultado.scalar_one()


async def _listar_eventos(
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
    codigo_rastreio: str,
) -> list[EventoWebhook]:
    async with fabrica_sessao_teste() as sessao:
        resultado = await sessao.execute(
            select(EventoWebhook)
            .join(Remessa)
            .where(Remessa.codigo_rastreio == codigo_rastreio)
            .order_by(EventoWebhook.id)
        )
        return list(resultado.scalars().all())


async def _contar_eventos(
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
    codigo_rastreio: str,
) -> int:
    async with fabrica_sessao_teste() as sessao:
        resultado = await sessao.execute(
            select(func.count())
            .select_from(EventoWebhook)
            .join(Remessa)
            .where(Remessa.codigo_rastreio == codigo_rastreio)
        )
        return resultado.scalar_one()


async def _contar_tentativas(
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> int:
    async with fabrica_sessao_teste() as sessao:
        resultado = await sessao.execute(select(func.count()).select_from(TentativaWebhook))
        return resultado.scalar_one()


# --- Cadastro de remessas ---


async def test_post_remessa_cria_201_com_status_aguardando_envio(
    cliente: httpx.AsyncClient,
) -> None:
    resposta = await _criar_remessa(cliente)

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["id"] is not None
    assert corpo["codigo_rastreio"] == CODIGO
    assert corpo["vendedor"] == "Loja Exemplo LTDA"
    assert corpo["status"] == "AGUARDANDO_ENVIO"
    assert corpo["proximo_status"] == "POSTADO"
    assert corpo["url_callback"] == URL_CALLBACK
    assert corpo["entregue_em"] is None
    assert corpo["recebido_por"] is None
    assert corpo["criado_em"] is not None
    assert corpo["atualizado_em"] is not None


async def test_post_remessa_repetido_retorna_200_sem_alterar(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    primeira = await _criar_remessa(cliente)
    assert primeira.status_code == 201

    segunda = await _criar_remessa(
        cliente,
        vendedor="Outro Vendedor",
        url_callback="http://outro/callback",
    )

    assert segunda.status_code == 200
    corpo = segunda.json()
    assert corpo["id"] == primeira.json()["id"]
    assert corpo["vendedor"] == "Loja Exemplo LTDA"
    assert corpo["url_callback"] == URL_CALLBACK
    assert corpo["status"] == "AGUARDANDO_ENVIO"
    assert corpo["proximo_status"] == "POSTADO"
    assert await _contar_remessas(fabrica_sessao_teste) == 1
    assert await _contar_eventos(fabrica_sessao_teste, CODIGO) == 0


async def test_post_remessa_com_token_de_admin_retorna_403(
    cliente: httpx.AsyncClient,
) -> None:
    token = await _login_admin(cliente)

    resposta = await cliente.post(
        "/remessas",
        json={
            "codigo_rastreio": CODIGO,
            "vendedor": "Loja Exemplo LTDA",
            "url_callback": URL_CALLBACK,
        },
        headers=_cabecalho_admin(token),
    )

    assert resposta.status_code == 403
    assert resposta.json()["codigo"] == "PERMISSAO_INSUFICIENTE"


async def test_get_remessa_por_codigo_com_chave_de_servico_retorna_200(
    cliente: httpx.AsyncClient,
) -> None:
    await _criar_remessa(cliente)

    resposta = await cliente.get(f"/remessas/{CODIGO}", headers=_cabecalho_chave())

    assert resposta.status_code == 200
    assert resposta.json()["codigo_rastreio"] == CODIGO
    assert resposta.json()["proximo_status"] == "POSTADO"


async def test_get_remessa_por_codigo_com_admin_retorna_200(
    cliente: httpx.AsyncClient,
) -> None:
    token = await _login_admin(cliente)
    await _criar_remessa(cliente)

    resposta = await cliente.get(f"/remessas/{CODIGO}", headers=_cabecalho_admin(token))

    assert resposta.status_code == 200
    assert resposta.json()["codigo_rastreio"] == CODIGO
    assert resposta.json()["proximo_status"] == "POSTADO"


async def test_get_remessa_inexistente_retorna_404(
    cliente: httpx.AsyncClient,
) -> None:
    token = await _login_admin(cliente)

    resposta = await cliente.get("/remessas/NAOEXISTE", headers=_cabecalho_admin(token))

    assert resposta.status_code == 404
    assert resposta.json()["codigo"] == "REMESSA_NAO_ENCONTRADA"


async def test_get_remessas_com_chave_de_servico_retorna_403(
    cliente: httpx.AsyncClient,
) -> None:
    resposta = await cliente.get("/remessas", headers=_cabecalho_chave())

    assert resposta.status_code == 403
    assert resposta.json()["codigo"] == "PERMISSAO_INSUFICIENTE"


async def test_get_remessas_com_admin_lista_da_mais_recente_para_a_mais_antiga(
    cliente: httpx.AsyncClient,
) -> None:
    token = await _login_admin(cliente)
    await _criar_remessa(cliente, codigo_rastreio="BR111111111")
    await _criar_remessa(cliente, codigo_rastreio="BR222222222")

    resposta = await cliente.get("/remessas", headers=_cabecalho_admin(token))

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert [remessa["codigo_rastreio"] for remessa in corpo] == [
        "BR222222222",
        "BR111111111",
    ]
    assert all(remessa["proximo_status"] == "POSTADO" for remessa in corpo)


# --- Mudança de status ---


async def test_sequencia_valida_passo_a_passo(
    cliente: httpx.AsyncClient,
) -> None:
    token = await _login_admin(cliente)
    await _criar_remessa(cliente)

    for status, proximo in [
        ("POSTADO", "EM_TRANSITO"),
        ("EM_TRANSITO", "SAIU_PARA_ENTREGA"),
        ("SAIU_PARA_ENTREGA", "ENTREGUE"),
    ]:
        resposta = await _mudar_status(cliente, token, CODIGO, status)
        assert resposta.status_code == 200
        assert resposta.json()["status"] == status
        assert resposta.json()["proximo_status"] == proximo

    resposta = await _entregar(cliente, token, CODIGO, recebido_por="Maria Souza")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["status"] == "ENTREGUE"
    assert corpo["proximo_status"] is None
    assert corpo["entregue_em"] is not None
    assert corpo["recebido_por"] == "Maria Souza"


async def test_pular_uma_etapa_retorna_409_e_nao_altera_nada(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    token = await _login_admin(cliente)
    await _criar_remessa(cliente)

    resposta = await _mudar_status(cliente, token, CODIGO, "EM_TRANSITO")

    assert resposta.status_code == 409
    assert resposta.json()["codigo"] == "TRANSICAO_INVALIDA"
    remessa = await _obter_remessa(fabrica_sessao_teste, CODIGO)
    assert remessa is not None
    assert remessa.status == "AGUARDANDO_ENVIO"
    assert await _contar_eventos(fabrica_sessao_teste, CODIGO) == 0


async def test_repetir_o_status_atual_retorna_409(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    token = await _login_admin(cliente)
    await _criar_remessa(cliente)
    await _avancar_ate(cliente, token, CODIGO, "POSTADO")

    resposta = await _mudar_status(cliente, token, CODIGO, "POSTADO")

    assert resposta.status_code == 409
    assert resposta.json()["codigo"] == "TRANSICAO_INVALIDA"
    remessa = await _obter_remessa(fabrica_sessao_teste, CODIGO)
    assert remessa is not None
    assert remessa.status == "POSTADO"
    assert await _contar_eventos(fabrica_sessao_teste, CODIGO) == 1


async def test_voltar_o_status_retorna_409(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    token = await _login_admin(cliente)
    await _criar_remessa(cliente)
    await _avancar_ate(cliente, token, CODIGO, "EM_TRANSITO")

    resposta = await _mudar_status(cliente, token, CODIGO, "POSTADO")

    assert resposta.status_code == 409
    assert resposta.json()["codigo"] == "TRANSICAO_INVALIDA"
    remessa = await _obter_remessa(fabrica_sessao_teste, CODIGO)
    assert remessa is not None
    assert remessa.status == "EM_TRANSITO"
    assert await _contar_eventos(fabrica_sessao_teste, CODIGO) == 2


@pytest.mark.parametrize(
    "status_invalido",
    ["ENTREGUE", "AGUARDANDO_ENVIO", "INVALIDO"],
)
async def test_status_fora_dos_tres_permitidos_retorna_422(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
    status_invalido: str,
) -> None:
    token = await _login_admin(cliente)
    await _criar_remessa(cliente)

    resposta = await _mudar_status(cliente, token, CODIGO, status_invalido)

    assert resposta.status_code == 422
    remessa = await _obter_remessa(fabrica_sessao_teste, CODIGO)
    assert remessa is not None
    assert remessa.status == "AGUARDANDO_ENVIO"
    assert await _contar_eventos(fabrica_sessao_teste, CODIGO) == 0


@pytest.mark.parametrize("status_atual", [None, "POSTADO", "EM_TRANSITO"])
async def test_entregar_fora_de_saiu_para_entrega_retorna_409(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
    status_atual: str | None,
) -> None:
    token = await _login_admin(cliente)
    await _criar_remessa(cliente)
    if status_atual is not None:
        await _avancar_ate(cliente, token, CODIGO, status_atual)
    eventos_antes = await _contar_eventos(fabrica_sessao_teste, CODIGO)

    resposta = await _entregar(cliente, token, CODIGO)

    assert resposta.status_code == 409
    assert resposta.json()["codigo"] == "TRANSICAO_INVALIDA"
    remessa = await _obter_remessa(fabrica_sessao_teste, CODIGO)
    assert remessa is not None
    assert remessa.status == (status_atual or "AGUARDANDO_ENVIO")
    assert await _contar_eventos(fabrica_sessao_teste, CODIGO) == eventos_antes


# --- Eventos gerados ---


async def test_mudanca_de_status_cria_um_evento_com_corpo_do_contrato(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    token = await _login_admin(cliente)
    await _criar_remessa(cliente)

    resposta = await _mudar_status(cliente, token, CODIGO, "POSTADO")

    assert resposta.status_code == 200
    eventos = await _listar_eventos(fabrica_sessao_teste, CODIGO)
    assert len(eventos) == 1
    evento = eventos[0]
    assert evento.tipo_evento == "remessa.status_alterado"
    assert evento.estado == EstadoEnvio.PENDENTE.value
    assert evento.total_tentativas == 0
    assert evento.proxima_tentativa_em is not None

    corpo = json.loads(evento.corpo)
    assert corpo["id_evento"] == evento.id_evento
    assert uuid.UUID(corpo["id_evento"]).version == 4
    assert corpo["tipo_evento"] == "remessa.status_alterado"
    assert corpo["codigo_rastreio"] == CODIGO
    assert corpo["status"] == "POSTADO"
    assert corpo["vendedor"] == "Loja Exemplo LTDA"
    assert corpo["ocorrido_em"].endswith("Z")
    assert "entregue_em" not in corpo
    assert "recebido_por" not in corpo


async def test_entrega_cria_evento_remessa_entregue_com_entregue_em_e_recebido_por(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    token = await _login_admin(cliente)
    await _criar_remessa(cliente)
    await _avancar_ate(cliente, token, CODIGO, "SAIU_PARA_ENTREGA")
    eventos_antes = await _contar_eventos(fabrica_sessao_teste, CODIGO)

    resposta = await _entregar(cliente, token, CODIGO, recebido_por="Maria Souza")

    assert resposta.status_code == 200
    eventos = await _listar_eventos(fabrica_sessao_teste, CODIGO)
    assert len(eventos) == eventos_antes + 1
    evento = eventos[-1]
    assert evento.tipo_evento == "remessa.entregue"

    corpo = json.loads(evento.corpo)
    assert corpo["id_evento"] == evento.id_evento
    assert corpo["tipo_evento"] == "remessa.entregue"
    assert corpo["codigo_rastreio"] == CODIGO
    assert corpo["status"] == "ENTREGUE"
    assert corpo["vendedor"] == "Loja Exemplo LTDA"
    assert corpo["ocorrido_em"].endswith("Z")
    assert corpo["entregue_em"].endswith("Z")
    assert corpo["recebido_por"] == "Maria Souza"


async def test_mudanca_de_status_nao_registra_tentativa_de_envio(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    token = await _login_admin(cliente)
    await _criar_remessa(cliente)

    resposta = await _mudar_status(cliente, token, CODIGO, "POSTADO")

    assert resposta.status_code == 200
    eventos = await _listar_eventos(fabrica_sessao_teste, CODIGO)
    assert len(eventos) == 1
    assert eventos[0].estado == EstadoEnvio.PENDENTE.value
    assert eventos[0].total_tentativas == 0
    assert await _contar_tentativas(fabrica_sessao_teste) == 0


async def test_falha_ao_gravar_evento_nao_altera_remessa(
    cliente: httpx.AsyncClient,
    motor_teste,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    token = await _login_admin(cliente)
    await _criar_remessa(cliente)

    async with motor_teste.begin() as conexao:
        await conexao.execute(text("DROP TRIGGER IF EXISTS falhar_evento_teste ON eventos_webhook"))
        await conexao.execute(text("DROP FUNCTION IF EXISTS falhar_evento_teste()"))
        await conexao.execute(
            text(
                """
                CREATE FUNCTION falhar_evento_teste() RETURNS trigger AS $$
                BEGIN
                    RAISE EXCEPTION 'falha simulada ao gravar evento';
                END;
                $$ LANGUAGE plpgsql
                """
            )
        )
        await conexao.execute(
            text(
                """
                CREATE TRIGGER falhar_evento_teste
                BEFORE INSERT ON eventos_webhook
                FOR EACH ROW EXECUTE FUNCTION falhar_evento_teste()
                """
            )
        )

    try:
        transporte = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transporte,
            base_url="http://teste",
        ) as cliente_sem_excecao:
            resposta = await cliente_sem_excecao.post(
                f"/remessas/{CODIGO}/status",
                json={"status": "POSTADO"},
                headers=_cabecalho_admin(token),
            )
    finally:
        async with motor_teste.begin() as conexao:
            await conexao.execute(
                text("DROP TRIGGER IF EXISTS falhar_evento_teste ON eventos_webhook")
            )
            await conexao.execute(text("DROP FUNCTION IF EXISTS falhar_evento_teste()"))

    assert resposta.status_code == 500
    remessa = await _obter_remessa(fabrica_sessao_teste, CODIGO)
    assert remessa is not None
    assert remessa.status == "AGUARDANDO_ENVIO"
    assert await _contar_eventos(fabrica_sessao_teste, CODIGO) == 0


# --- Autorização das rotas de status ---


@pytest.mark.parametrize(
    "caminho",
    [f"/remessas/{CODIGO}/status", f"/remessas/{CODIGO}/entregar"],
)
async def test_rotas_de_status_com_chave_de_servico_retornam_403(
    cliente: httpx.AsyncClient,
    caminho: str,
) -> None:
    await _criar_remessa(cliente)
    corpo = {"status": "POSTADO"} if caminho.endswith("/status") else {}

    resposta = await cliente.post(caminho, json=corpo, headers=_cabecalho_chave())

    assert resposta.status_code == 403
    assert resposta.json()["codigo"] == "PERMISSAO_INSUFICIENTE"


@pytest.mark.parametrize(
    "caminho",
    [f"/remessas/{CODIGO}/status", f"/remessas/{CODIGO}/entregar"],
)
async def test_rotas_de_status_sem_credencial_retornam_401(
    cliente: httpx.AsyncClient,
    caminho: str,
) -> None:
    await _criar_remessa(cliente)
    corpo = {"status": "POSTADO"} if caminho.endswith("/status") else {}

    resposta = await cliente.post(caminho, json=corpo)

    assert resposta.status_code == 401
    assert resposta.json()["codigo"] == "TOKEN_INVALIDO"


# --- Concorrência ---


async def test_cinco_posts_simultaneos_do_mesmo_codigo_um_201_e_quatro_200(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    respostas = await asyncio.gather(*[_criar_remessa(cliente) for _ in range(5)])

    assert sorted(resposta.status_code for resposta in respostas) == [200, 200, 200, 200, 201]
    assert len({resposta.json()["id"] for resposta in respostas}) == 1
    assert await _contar_remessas(fabrica_sessao_teste) == 1
    assert await _contar_eventos(fabrica_sessao_teste, CODIGO) == 0


async def test_cinco_status_simultaneos_para_o_mesmo_proximo_status_um_200_e_quatro_409(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    token = await _login_admin(cliente)
    await _criar_remessa(cliente)

    respostas = await asyncio.gather(
        *[_mudar_status(cliente, token, CODIGO, "POSTADO") for _ in range(5)]
    )

    assert sorted(resposta.status_code for resposta in respostas) == [
        200,
        409,
        409,
        409,
        409,
    ]
    for resposta in respostas:
        if resposta.status_code == 409:
            assert resposta.json()["codigo"] == "TRANSICAO_INVALIDA"

    remessa = await _obter_remessa(fabrica_sessao_teste, CODIGO)
    assert remessa is not None
    assert remessa.status == StatusRemessa.POSTADO.value
    assert await _contar_eventos(fabrica_sessao_teste, CODIGO) == 1
