from collections.abc import AsyncIterator

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.configuracao import obter_configuracao

CONVENCAO_NOMES = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

METADATA = MetaData(naming_convention=CONVENCAO_NOMES)

configuracao = obter_configuracao()

motor = create_async_engine(
    configuracao.url_banco,
    pool_size=configuracao.tamanho_pool_banco,
    pool_pre_ping=True,
)

FabricaSessao = async_sessionmaker(motor, expire_on_commit=False)


async def obter_motor() -> AsyncEngine:
    return motor


async def obter_sessao() -> AsyncIterator[AsyncSession]:
    async with FabricaSessao() as sessao:
        yield sessao
