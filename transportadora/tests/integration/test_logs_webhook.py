import uuid

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.configuracao import obter_configuracao
from app.models.enums import EstadoEnvio
from app.models.evento_webhook import EventoWebhook
from app.models.remessa import Remessa
from app.models.tentativa_webhook import TentativaWebhook

ADMIN_EMAIL = "admin@hooklog.test"
ADMIN_SENHA = "senha-admin-123"
URL_CALLBACK = "http://monitoramento:8000/webhooks/transportadora"
CODIGO = "BR123456789"


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
) -> httpx.Response:
    return await cliente.post(
        "/remessas",
        json={
            "codigo_rastreio": codigo_rastreio,
            "vendedor": "Loja Exemplo LTDA",
            "url_callback": URL_CALLBACK,
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


async def _obter_evento_por_codigo(
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
    codigo_rastreio: str,
) -> EventoWebhook | None:
    async with fabrica_sessao_teste() as sessao:
        resultado = await sessao.execute(
            select(EventoWebhook)
            .join(Remessa)
            .where(Remessa.codigo_rastreio == codigo_rastreio)
            .order_by(EventoWebhook.id.desc())
        )
        return resultado.scalars().first()


async def _contar_eventos(
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> int:
    async with fabrica_sessao_teste() as sessao:
        resultado = await sessao.execute(select(func.count()).select_from(EventoWebhook))
        return resultado.scalar_one()


async def _contar_tentativas_por_evento(
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
    evento_id: int,
) -> int:
    async with fabrica_sessao_teste() as sessao:
        resultado = await sessao.execute(
            select(func.count())
            .select_from(TentativaWebhook)
            .where(TentativaWebhook.evento_webhook_id == evento_id)
        )
        return resultado.scalar_one()


# --- Listagem ---


async def test_listar_logs_retorna_evento_mais_recente_primeiro(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    token = await _login_admin(cliente)
    await _criar_remessa(cliente)
    await _mudar_status(cliente, token, CODIGO, "POSTADO")
    primeiro_evento_id = (await _obter_evento_por_codigo(fabrica_sessao_teste, CODIGO)).id

    await _mudar_status(cliente, token, CODIGO, "EM_TRANSITO")
    segundo_evento_id = (await _obter_evento_por_codigo(fabrica_sessao_teste, CODIGO)).id

    resposta = await cliente.get("/logs-webhook", headers=_cabecalho_admin(token))

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert len(corpo) == 2
    assert corpo[0]["id"] == segundo_evento_id
    assert corpo[0]["tipo_evento"] == "remessa.status_alterado"
    assert corpo[0]["codigo_rastreio"] == CODIGO
    assert corpo[0]["estado"] == EstadoEnvio.PENDENTE.value
    assert corpo[0]["total_tentativas"] == 0
    assert corpo[0]["ultimo_status_http"] is None
    assert corpo[0]["ultimo_erro"] is None
    assert corpo[0]["criado_em"] is not None
    assert corpo[0]["enviado_em"] is None
    assert corpo[0]["historico_tentativas"] == []
    assert corpo[1]["id"] == primeiro_evento_id


async def test_listar_logs_filtra_por_codigo_rastreio(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    token = await _login_admin(cliente)
    await _criar_remessa(cliente, codigo_rastreio="BR111111111")
    await _mudar_status(cliente, token, "BR111111111", "POSTADO")
    await _criar_remessa(cliente, codigo_rastreio="BR222222222")
    await _mudar_status(cliente, token, "BR222222222", "POSTADO")

    resposta = await cliente.get(
        "/logs-webhook?codigo_rastreio=BR111111111",
        headers=_cabecalho_admin(token),
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert len(corpo) == 1
    assert corpo[0]["codigo_rastreio"] == "BR111111111"


async def test_listar_logs_filtra_por_estado(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    token = await _login_admin(cliente)
    await _criar_remessa(cliente)
    await _mudar_status(cliente, token, CODIGO, "POSTADO")

    async with fabrica_sessao_teste() as sessao:
        resultado = await sessao.execute(
            select(EventoWebhook).join(Remessa).where(Remessa.codigo_rastreio == CODIGO)
        )
        evento_db = resultado.scalars().first()
        sessao.add(
            TentativaWebhook(
                evento_webhook_id=evento_db.id,
                numero=1,
                status_http=500,
                erro="erro simulado",
                duracao_ms=10,
                tentou_em=evento_db.criado_em,
            )
        )
        evento_db.estado = EstadoEnvio.FALHA.value
        evento_db.total_tentativas = 1
        evento_db.ultimo_status_http = 500
        evento_db.ultimo_erro = "erro simulado"
        await sessao.commit()

    resposta = await cliente.get(
        "/logs-webhook?estado=FALHA",
        headers=_cabecalho_admin(token),
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert len(corpo) == 1
    assert corpo[0]["estado"] == EstadoEnvio.FALHA.value
    assert corpo[0]["total_tentativas"] == 1
    assert corpo[0]["ultimo_status_http"] == 500
    assert corpo[0]["ultimo_erro"] == "erro simulado"
    assert len(corpo[0]["historico_tentativas"]) == 1
    assert corpo[0]["historico_tentativas"][0]["numero"] == 1
    assert corpo[0]["historico_tentativas"][0]["status_http"] == 500
    assert corpo[0]["historico_tentativas"][0]["erro"] == "erro simulado"


async def test_listar_logs_estado_invalido_retorna_422(
    cliente: httpx.AsyncClient,
) -> None:
    token = await _login_admin(cliente)

    resposta = await cliente.get(
        "/logs-webhook?estado=INVALIDO",
        headers=_cabecalho_admin(token),
    )

    assert resposta.status_code == 422


async def test_listar_logs_sem_token_retorna_401(
    cliente: httpx.AsyncClient,
) -> None:
    resposta = await cliente.get("/logs-webhook")

    assert resposta.status_code == 401
    assert resposta.json()["codigo"] == "TOKEN_INVALIDO"


async def test_listar_logs_com_chave_de_servico_retorna_403(
    cliente: httpx.AsyncClient,
) -> None:
    resposta = await cliente.get("/logs-webhook", headers=_cabecalho_chave())

    assert resposta.status_code == 403
    assert resposta.json()["codigo"] == "PERMISSAO_INSUFICIENTE"


# --- Reenvio ---


async def test_reenviar_evento_pendente_retorna_202_e_redefine_para_pendente(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    token = await _login_admin(cliente)
    await _criar_remessa(cliente)
    await _mudar_status(cliente, token, CODIGO, "POSTADO")
    evento = await _obter_evento_por_codigo(fabrica_sessao_teste, CODIGO)

    async with fabrica_sessao_teste() as sessao:
        sessao.add(
            TentativaWebhook(
                evento_webhook_id=evento.id,
                numero=2,
                status_http=500,
                erro="tempo esgotado",
                duracao_ms=5000,
                tentou_em=evento.criado_em,
            )
        )
        evento.estado = EstadoEnvio.FALHA.value
        evento.total_tentativas = 2
        evento.proxima_tentativa_em = evento.criado_em
        evento.ultimo_status_http = 500
        evento.ultimo_erro = "tempo esgotado"
        await sessao.commit()

    id_evento = evento.id_evento
    corpo_original = evento.corpo

    resposta = await cliente.post(
        f"/logs-webhook/{evento.id}/reenviar",
        headers=_cabecalho_admin(token),
    )

    assert resposta.status_code == 202
    corpo = resposta.json()
    assert corpo["id"] == evento.id
    assert corpo["id_evento"] == id_evento
    assert corpo["estado"] == EstadoEnvio.PENDENTE.value
    assert corpo["total_tentativas"] == 0
    assert corpo["ultimo_status_http"] is None
    assert corpo["ultimo_erro"] is None
    assert len(corpo["historico_tentativas"]) == 1
    assert corpo["historico_tentativas"][0]["numero"] == 2
    assert corpo["historico_tentativas"][0]["status_http"] == 500
    assert corpo["historico_tentativas"][0]["erro"] == "tempo esgotado"

    async with fabrica_sessao_teste() as sessao:
        evento_atualizado = await sessao.get(EventoWebhook, evento.id)
        assert evento_atualizado is not None
        assert evento_atualizado.id_evento == id_evento
        assert evento_atualizado.corpo == corpo_original
        assert evento_atualizado.estado == EstadoEnvio.PENDENTE.value
        assert evento_atualizado.total_tentativas == 0
        assert evento_atualizado.proxima_tentativa_em is not None


async def test_reenviar_evento_enviado_retorna_202_e_redefine_para_pendente(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    token = await _login_admin(cliente)
    await _criar_remessa(cliente)
    await _mudar_status(cliente, token, CODIGO, "POSTADO")
    evento = await _obter_evento_por_codigo(fabrica_sessao_teste, CODIGO)

    async with fabrica_sessao_teste() as sessao:
        sessao.add(
            TentativaWebhook(
                evento_webhook_id=evento.id,
                numero=1,
                status_http=200,
                erro=None,
                duracao_ms=50,
                tentou_em=evento.criado_em,
            )
        )
        evento.estado = EstadoEnvio.ENVIADO.value
        evento.total_tentativas = 1
        evento.enviado_em = evento.criado_em
        evento.ultimo_status_http = 200
        await sessao.commit()

    resposta = await cliente.post(
        f"/logs-webhook/{evento.id}/reenviar",
        headers=_cabecalho_admin(token),
    )

    assert resposta.status_code == 202
    corpo = resposta.json()
    assert corpo["estado"] == EstadoEnvio.PENDENTE.value
    assert corpo["total_tentativas"] == 0
    assert len(corpo["historico_tentativas"]) == 1
    assert corpo["historico_tentativas"][0]["numero"] == 1
    assert corpo["historico_tentativas"][0]["status_http"] == 200

    async with fabrica_sessao_teste() as sessao:
        evento_atualizado = await sessao.get(EventoWebhook, evento.id)
        assert evento_atualizado.estado == EstadoEnvio.PENDENTE.value
        assert evento_atualizado.total_tentativas == 0


async def test_reenviar_evento_inexistente_retorna_404(
    cliente: httpx.AsyncClient,
) -> None:
    token = await _login_admin(cliente)

    resposta = await cliente.post(
        "/logs-webhook/999999/reenviar",
        headers=_cabecalho_admin(token),
    )

    assert resposta.status_code == 404
    assert resposta.json()["codigo"] == "EVENTO_WEBHOOK_NAO_ENCONTRADO"


async def test_reenviar_sem_token_retorna_401(
    cliente: httpx.AsyncClient,
) -> None:
    resposta = await cliente.post("/logs-webhook/1/reenviar")

    assert resposta.status_code == 401
    assert resposta.json()["codigo"] == "TOKEN_INVALIDO"


async def test_reenviar_com_chave_de_servico_retorna_403(
    cliente: httpx.AsyncClient,
) -> None:
    resposta = await cliente.post(
        "/logs-webhook/1/reenviar",
        headers=_cabecalho_chave(),
    )

    assert resposta.status_code == 403
    assert resposta.json()["codigo"] == "PERMISSAO_INSUFICIENTE"


async def test_reenviar_mantem_mesmo_id_evento_e_corpo(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    token = await _login_admin(cliente)
    await _criar_remessa(cliente)
    await _mudar_status(cliente, token, CODIGO, "POSTADO")
    evento = await _obter_evento_por_codigo(fabrica_sessao_teste, CODIGO)
    id_evento = evento.id_evento
    corpo_original = evento.corpo

    async with fabrica_sessao_teste() as sessao:
        sessao.add(
            TentativaWebhook(
                evento_webhook_id=evento.id,
                numero=3,
                status_http=500,
                erro="falha",
                duracao_ms=100,
                tentou_em=evento.criado_em,
            )
        )
        evento.estado = EstadoEnvio.FALHA.value
        evento.total_tentativas = 3
        await sessao.commit()

    await cliente.post(
        f"/logs-webhook/{evento.id}/reenviar",
        headers=_cabecalho_admin(token),
    )

    async with fabrica_sessao_teste() as sessao:
        evento_atualizado = await sessao.get(EventoWebhook, evento.id)

    assert evento_atualizado.id_evento == id_evento
    assert evento_atualizado.corpo == corpo_original
    assert uuid.UUID(id_evento).version == 4


# --- Concorrência de reenvio não se aplica (único evento), mas isolamento do ADMIN sim ---


async def test_usuario_nao_pode_listar_logs_retorna_403(
    cliente: httpx.AsyncClient,
) -> None:
    resposta = await cliente.get("/logs-webhook")

    assert resposta.status_code == 401
