from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Annotated

import httpx
import jwt
import pytest_asyncio
from fastapi import Depends, FastAPI

from app.core.configuracao import obter_configuracao
from app.core.dependencias import exigir_admin, exigir_chave_servico
from app.core.erros import ErroDeDominio, manipulador_erro_dominio
from app.core.seguranca import CredencialAutenticada, criar_token_acesso
from app.models.enums import Papel

app_teste = FastAPI()
app_teste.add_exception_handler(ErroDeDominio, manipulador_erro_dominio)


@app_teste.get("/teste/admin")
async def rota_admin(
    credencial: Annotated[CredencialAutenticada, Depends(exigir_admin)],
) -> dict[str, str]:
    return {"papel": credencial.papel.value}


@app_teste.get("/teste/chave-servico")
async def rota_chave_servico(
    credencial: Annotated[None, Depends(exigir_chave_servico)],
) -> dict[str, bool]:
    return {"ok": True}


@pytest_asyncio.fixture
async def cliente_teste() -> AsyncIterator[httpx.AsyncClient]:
    transporte = httpx.ASGITransport(app=app_teste)
    async with httpx.AsyncClient(transport=transporte, base_url="http://teste") as http:
        yield http


def _token_de_admin() -> str:
    return criar_token_acesso("admin", Papel.ADMIN)


def _token_de_outro_servico() -> str:
    return jwt.encode(
        {
            "sub": "admin",
            "papel": "ADMIN",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        "segredo-jwt-do-monitoramento-com-32-bytes",
        algorithm="HS256",
    )


def _chave_api() -> str:
    return obter_configuracao().chave_api_servico


async def test_rota_admin_sem_credencial_retorna_401(
    cliente_teste: httpx.AsyncClient,
) -> None:
    resposta = await cliente_teste.get("/teste/admin")

    assert resposta.status_code == 401
    assert resposta.json()["codigo"] == "TOKEN_INVALIDO"


async def test_rota_admin_com_token_de_outro_servico_retorna_401(
    cliente_teste: httpx.AsyncClient,
) -> None:
    resposta = await cliente_teste.get(
        "/teste/admin",
        headers={"Authorization": f"Bearer {_token_de_outro_servico()}"},
    )

    assert resposta.status_code == 401
    assert resposta.json()["codigo"] == "TOKEN_INVALIDO"


async def test_rota_admin_com_chave_de_servico_retorna_403(
    cliente_teste: httpx.AsyncClient,
) -> None:
    resposta = await cliente_teste.get(
        "/teste/admin",
        headers={"X-Chave-Api": _chave_api()},
    )

    assert resposta.status_code == 403
    assert resposta.json()["codigo"] == "PERMISSAO_INSUFICIENTE"


async def test_rota_admin_com_token_de_admin_retorna_200(
    cliente_teste: httpx.AsyncClient,
) -> None:
    resposta = await cliente_teste.get(
        "/teste/admin",
        headers={"Authorization": f"Bearer {_token_de_admin()}"},
    )

    assert resposta.status_code == 200
    assert resposta.json() == {"papel": "ADMIN"}


async def test_rota_chave_servico_sem_credencial_retorna_401(
    cliente_teste: httpx.AsyncClient,
) -> None:
    resposta = await cliente_teste.get("/teste/chave-servico")

    assert resposta.status_code == 401
    assert resposta.json()["codigo"] == "CHAVE_API_INVALIDA"


async def test_rota_chave_servico_com_chave_errada_retorna_401(
    cliente_teste: httpx.AsyncClient,
) -> None:
    resposta = await cliente_teste.get(
        "/teste/chave-servico",
        headers={"X-Chave-Api": "chave-errada"},
    )

    assert resposta.status_code == 401
    assert resposta.json()["codigo"] == "CHAVE_API_INVALIDA"


async def test_rota_chave_servico_com_token_de_admin_retorna_403(
    cliente_teste: httpx.AsyncClient,
) -> None:
    resposta = await cliente_teste.get(
        "/teste/chave-servico",
        headers={"Authorization": f"Bearer {_token_de_admin()}"},
    )

    assert resposta.status_code == 403
    assert resposta.json()["codigo"] == "PERMISSAO_INSUFICIENTE"


async def test_rota_chave_servico_com_chave_correta_retorna_200(
    cliente_teste: httpx.AsyncClient,
) -> None:
    resposta = await cliente_teste.get(
        "/teste/chave-servico",
        headers={"X-Chave-Api": _chave_api()},
    )

    assert resposta.status_code == 200
    assert resposta.json() == {"ok": True}
