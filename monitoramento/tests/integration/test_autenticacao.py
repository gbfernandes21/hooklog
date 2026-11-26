import asyncio
import logging
from datetime import UTC, datetime, timedelta

import httpx
import jwt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.configuracao import obter_configuracao
from app.models.usuario import Usuario

ADMIN_EMAIL = "admin@hooklog.test"
ADMIN_SENHA = "senha-admin-123"


def _decodificar_token(token: str) -> dict:
    return jwt.decode(
        token,
        obter_configuracao().segredo_jwt,
        algorithms=["HS256"],
    )


async def _registrar(
    cliente: httpx.AsyncClient,
    email: str = "ana@exemplo.com",
    senha: str = "minhasenha123",
) -> dict:
    resposta = await cliente.post(
        "/autenticacao/registro",
        json={"email": email, "senha": senha},
    )
    assert resposta.status_code == 201
    return resposta.json()


async def _login(
    cliente: httpx.AsyncClient,
    email: str,
    senha: str,
) -> httpx.Response:
    return await cliente.post(
        "/autenticacao/login",
        data={"username": email, "password": senha},
    )


async def _contar_usuarios(
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> int:
    async with fabrica_sessao_teste() as sessao:
        resultado = await sessao.execute(select(func.count()).select_from(Usuario))
        return resultado.scalar_one()


async def test_registro_cria_usuario_com_papel_user(cliente: httpx.AsyncClient) -> None:
    resposta = await cliente.post(
        "/autenticacao/registro",
        json={"email": "Ana@Exemplo.com", "senha": "minhasenha123"},
    )

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert isinstance(corpo["id"], int)
    assert corpo["email"] == "ana@exemplo.com"
    assert corpo["papel"] == "USER"
    assert "criado_em" in corpo


async def test_registro_com_email_duplicado_retorna_409(cliente: httpx.AsyncClient) -> None:
    await _registrar(cliente, email="ana@exemplo.com")

    resposta = await cliente.post(
        "/autenticacao/registro",
        json={"email": "ANA@EXEMPLO.COM", "senha": "outrasenha123"},
    )

    assert resposta.status_code == 409
    assert resposta.json()["codigo"] == "EMAIL_JA_CADASTRADO"


async def test_registro_com_admin_email_retorna_409_e_nao_persiste(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    resposta = await cliente.post(
        "/autenticacao/registro",
        json={"email": ADMIN_EMAIL, "senha": "minhasenha123"},
    )

    assert resposta.status_code == 409
    assert resposta.json()["codigo"] == "EMAIL_JA_CADASTRADO"
    assert await _contar_usuarios(fabrica_sessao_teste) == 0


async def test_registro_com_email_invalido_retorna_422(cliente: httpx.AsyncClient) -> None:
    resposta = await cliente.post(
        "/autenticacao/registro",
        json={"email": "nao-e-um-email", "senha": "minhasenha123"},
    )

    assert resposta.status_code == 422
    assert "detail" in resposta.json()


async def test_registro_com_senha_curta_retorna_422(cliente: httpx.AsyncClient) -> None:
    resposta = await cliente.post(
        "/autenticacao/registro",
        json={"email": "ana@exemplo.com", "senha": "1234567"},
    )

    assert resposta.status_code == 422
    assert "detail" in resposta.json()


async def test_login_de_usuario_retorna_token_com_sub_e_papel_user(
    cliente: httpx.AsyncClient,
) -> None:
    usuario = await _registrar(cliente)

    resposta = await _login(cliente, "ana@exemplo.com", "minhasenha123")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["token_type"] == "bearer"
    payload = _decodificar_token(corpo["access_token"])
    assert payload["sub"] == str(usuario["id"])
    assert payload["papel"] == "USER"


async def test_login_com_email_inexistente_e_senha_errada_tem_a_mesma_mensagem(
    cliente: httpx.AsyncClient,
) -> None:
    resposta_inexistente = await _login(cliente, "naoexiste@exemplo.com", "qualquersenha")
    await _registrar(cliente)
    resposta_senha_errada = await _login(cliente, "ana@exemplo.com", "senhaerrada")

    assert resposta_inexistente.status_code == 401
    assert resposta_senha_errada.status_code == 401
    corpo_inexistente = resposta_inexistente.json()
    corpo_senha_errada = resposta_senha_errada.json()
    assert corpo_inexistente["codigo"] == "CREDENCIAIS_INVALIDAS"
    assert corpo_senha_errada["codigo"] == "CREDENCIAIS_INVALIDAS"
    assert corpo_inexistente["detalhe"] == corpo_senha_errada["detalhe"]


async def test_login_de_admin_com_credencial_do_env_retorna_token_sem_usuario_no_banco(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    resposta = await _login(cliente, ADMIN_EMAIL, ADMIN_SENHA)

    assert resposta.status_code == 200
    payload = _decodificar_token(resposta.json()["access_token"])
    assert payload["sub"] == "admin"
    assert payload["papel"] == "ADMIN"
    assert await _contar_usuarios(fabrica_sessao_teste) == 0


async def test_login_de_admin_com_senha_errada_retorna_401(cliente: httpx.AsyncClient) -> None:
    resposta = await _login(cliente, ADMIN_EMAIL, "senha-errada")

    assert resposta.status_code == 401
    assert resposta.json()["codigo"] == "CREDENCIAIS_INVALIDAS"


async def test_eu_de_usuario_retorna_id_email_e_papel(cliente: httpx.AsyncClient) -> None:
    usuario = await _registrar(cliente)
    token = (await _login(cliente, "ana@exemplo.com", "minhasenha123")).json()["access_token"]

    resposta = await cliente.get(
        "/autenticacao/eu",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resposta.status_code == 200
    assert resposta.json() == {
        "id": usuario["id"],
        "email": "ana@exemplo.com",
        "papel": "USER",
    }


async def test_eu_de_admin_retorna_id_nulo(cliente: httpx.AsyncClient) -> None:
    token = (await _login(cliente, ADMIN_EMAIL, ADMIN_SENHA)).json()["access_token"]

    resposta = await cliente.get(
        "/autenticacao/eu",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resposta.status_code == 200
    assert resposta.json() == {
        "id": None,
        "email": ADMIN_EMAIL,
        "papel": "ADMIN",
    }


async def test_eu_sem_token_retorna_401(cliente: httpx.AsyncClient) -> None:
    resposta = await cliente.get("/autenticacao/eu")

    assert resposta.status_code == 401
    assert resposta.json()["codigo"] == "TOKEN_INVALIDO"


async def test_eu_com_token_invalido_retorna_401(cliente: httpx.AsyncClient) -> None:
    resposta = await cliente.get(
        "/autenticacao/eu",
        headers={"Authorization": "Bearer token-invalido"},
    )

    assert resposta.status_code == 401
    assert resposta.json()["codigo"] == "TOKEN_INVALIDO"


async def test_eu_com_token_expirado_retorna_401(cliente: httpx.AsyncClient) -> None:
    token = jwt.encode(
        {
            "sub": "1",
            "papel": "USER",
            "exp": datetime.now(UTC) - timedelta(minutes=1),
        },
        obter_configuracao().segredo_jwt,
        algorithm="HS256",
    )

    resposta = await cliente.get(
        "/autenticacao/eu",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resposta.status_code == 401
    assert resposta.json()["codigo"] == "TOKEN_EXPIRADO"


async def test_eu_com_token_de_user_com_sub_nao_numerico_retorna_401(
    cliente: httpx.AsyncClient,
) -> None:
    token = jwt.encode(
        {
            "sub": "nao-e-numero",
            "papel": "USER",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        obter_configuracao().segredo_jwt,
        algorithm="HS256",
    )

    resposta = await cliente.get(
        "/autenticacao/eu",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resposta.status_code == 401
    assert resposta.json()["codigo"] == "TOKEN_INVALIDO"


async def test_eu_com_token_de_admin_com_sub_diferente_de_admin_retorna_401(
    cliente: httpx.AsyncClient,
) -> None:
    token = jwt.encode(
        {
            "sub": "123",
            "papel": "ADMIN",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        obter_configuracao().segredo_jwt,
        algorithm="HS256",
    )

    resposta = await cliente.get(
        "/autenticacao/eu",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resposta.status_code == 401
    assert resposta.json()["codigo"] == "TOKEN_INVALIDO"


async def test_openapi_expoe_esquema_oauth2_para_o_botao_authorize(
    cliente: httpx.AsyncClient,
) -> None:
    resposta = await cliente.get("/openapi.json")

    assert resposta.status_code == 200
    esquemas = resposta.json()["components"]["securitySchemes"]
    assert any(esquema.get("type") == "oauth2" for esquema in esquemas.values())


async def test_senha_e_token_nao_aparecem_nos_logs(
    cliente: httpx.AsyncClient,
    caplog,
) -> None:
    with caplog.at_level(logging.DEBUG):
        await _registrar(cliente, senha="senha-secreta-123")
        resposta = await _login(cliente, "ana@exemplo.com", "senha-secreta-123")

    token = resposta.json()["access_token"]
    assert "senha-secreta-123" not in caplog.text
    assert token not in caplog.text


async def test_verificacoes_de_senha_simultaneas_nao_bloqueiam_o_laco(
    cliente: httpx.AsyncClient,
) -> None:
    await _registrar(cliente, email="ana@exemplo.com", senha="minhasenha123")

    parar = asyncio.Event()

    async def relogio() -> int:
        tiques = 0
        while not parar.is_set():
            await asyncio.sleep(0.01)
            tiques += 1
        return tiques

    tarefa_relogio = asyncio.create_task(relogio())
    await asyncio.sleep(0)

    respostas = await asyncio.gather(
        *[_login(cliente, "ana@exemplo.com", "minhasenha123") for _ in range(5)]
    )

    parar.set()
    tiques = await tarefa_relogio

    assert [resposta.status_code for resposta in respostas] == [200] * 5
    assert tiques > 1
