from datetime import UTC, datetime, timedelta

import httpx
import jwt

from app.core.configuracao import obter_configuracao

ADMIN_EMAIL = "admin@hooklog.test"
ADMIN_SENHA = "senha-admin-123"


def _decodificar_token(token: str) -> dict:
    return jwt.decode(
        token,
        obter_configuracao().segredo_jwt,
        algorithms=["HS256"],
    )


async def _login(
    cliente: httpx.AsyncClient,
    email: str,
    senha: str,
) -> httpx.Response:
    return await cliente.post(
        "/autenticacao/login",
        data={"username": email, "password": senha},
    )


async def test_login_de_admin_com_credencial_do_env_retorna_token(
    cliente: httpx.AsyncClient,
) -> None:
    resposta = await _login(cliente, ADMIN_EMAIL, ADMIN_SENHA)

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["token_type"] == "bearer"
    payload = _decodificar_token(corpo["access_token"])
    assert payload["sub"] == "admin"
    assert payload["papel"] == "ADMIN"


async def test_login_de_admin_com_email_em_maiusculas_retorna_200(
    cliente: httpx.AsyncClient,
) -> None:
    resposta = await _login(cliente, "ADMIN@HOOKLOG.TEST", ADMIN_SENHA)

    assert resposta.status_code == 200
    assert _decodificar_token(resposta.json()["access_token"])["papel"] == "ADMIN"


async def test_login_de_admin_com_senha_errada_retorna_401(
    cliente: httpx.AsyncClient,
) -> None:
    resposta = await _login(cliente, ADMIN_EMAIL, "senha-errada")

    assert resposta.status_code == 401
    assert resposta.json()["codigo"] == "CREDENCIAIS_INVALIDAS"


async def test_login_de_admin_com_email_errado_retorna_401(
    cliente: httpx.AsyncClient,
) -> None:
    resposta = await _login(cliente, "outro@hooklog.test", ADMIN_SENHA)

    assert resposta.status_code == 401
    assert resposta.json()["codigo"] == "CREDENCIAIS_INVALIDAS"


async def test_eu_de_admin_retorna_email_e_papel(cliente: httpx.AsyncClient) -> None:
    token = (await _login(cliente, ADMIN_EMAIL, ADMIN_SENHA)).json()["access_token"]

    resposta = await cliente.get(
        "/autenticacao/eu",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resposta.status_code == 200
    assert resposta.json() == {"email": ADMIN_EMAIL, "papel": "ADMIN"}


async def test_eu_sem_token_retorna_401(cliente: httpx.AsyncClient) -> None:
    resposta = await cliente.get("/autenticacao/eu")

    assert resposta.status_code == 401
    assert resposta.json()["codigo"] == "TOKEN_INVALIDO"


async def test_eu_com_token_de_outro_servico_retorna_401(cliente: httpx.AsyncClient) -> None:
    token = jwt.encode(
        {
            "sub": "admin",
            "papel": "ADMIN",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        "segredo-jwt-do-monitoramento-com-32-bytes",
        algorithm="HS256",
    )

    resposta = await cliente.get(
        "/autenticacao/eu",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resposta.status_code == 401
    assert resposta.json()["codigo"] == "TOKEN_INVALIDO"


async def test_eu_com_token_expirado_retorna_401(cliente: httpx.AsyncClient) -> None:
    token = jwt.encode(
        {
            "sub": "admin",
            "papel": "ADMIN",
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


async def test_openapi_expoe_esquema_oauth2_para_o_botao_authorize(
    cliente: httpx.AsyncClient,
) -> None:
    resposta = await cliente.get("/openapi.json")

    assert resposta.status_code == 200
    esquemas = resposta.json()["components"]["securitySchemes"]
    assert any(esquema.get("type") == "oauth2" for esquema in esquemas.values())
