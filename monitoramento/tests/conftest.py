import os
from collections.abc import AsyncIterator

import httpx
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

URL_BANCO_TESTE = os.environ.get(
    "URL_BANCO_TESTE",
    "postgresql+asyncpg://usuario_monitoramento:troque-me@localhost:5433/monitoramento_teste",
)

os.environ["ADMIN_EMAIL"] = "admin@hooklog.test"
os.environ["ADMIN_SENHA"] = "senha-admin-123"
os.environ["URL_BANCO"] = URL_BANCO_TESTE
os.environ["SEGREDO_JWT"] = "segredo-jwt-teste"
os.environ["SEGREDO_WEBHOOK"] = "segredo-webhook-teste"
os.environ["CHAVE_API_TRANSPORTADORA"] = "chave-api-teste"

from app.core.banco_dados import obter_motor, obter_sessao
from app.main import app
from app.models import Base

NOME_BANCO_TESTE = make_url(URL_BANCO_TESTE).database


async def _garantir_banco_teste() -> None:
    url_admin = make_url(URL_BANCO_TESTE).set(database="postgres")
    motor_admin = create_async_engine(url_admin, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    try:
        async with motor_admin.connect() as conexao:
            resultado = await conexao.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :nome"),
                {"nome": NOME_BANCO_TESTE},
            )
            if resultado.scalar_one_or_none() is None:
                await conexao.execute(text(f'CREATE DATABASE "{NOME_BANCO_TESTE}"'))
    finally:
        await motor_admin.dispose()


@pytest_asyncio.fixture
async def motor_teste() -> AsyncIterator[AsyncEngine]:
    await _garantir_banco_teste()

    motor = create_async_engine(URL_BANCO_TESTE, poolclass=NullPool)
    async with motor.begin() as conexao:
        await conexao.run_sync(Base.metadata.create_all)

    tabelas = ", ".join(f'"{tabela.name}"' for tabela in Base.metadata.sorted_tables)
    async with motor.begin() as conexao:
        await conexao.execute(text(f"TRUNCATE {tabelas} RESTART IDENTITY CASCADE"))

    try:
        yield motor
    finally:
        await motor.dispose()


@pytest_asyncio.fixture
async def fabrica_sessao_teste(
    motor_teste: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(motor_teste, expire_on_commit=False)


@pytest_asyncio.fixture
async def cliente(
    motor_teste: AsyncEngine,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> AsyncIterator[httpx.AsyncClient]:
    async def obter_sessao_teste() -> AsyncIterator[AsyncSession]:
        async with fabrica_sessao_teste() as sessao:
            yield sessao

    app.dependency_overrides[obter_motor] = lambda: motor_teste
    app.dependency_overrides[obter_sessao] = obter_sessao_teste

    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transporte, base_url="http://teste") as http:
        yield http

    app.dependency_overrides.clear()
