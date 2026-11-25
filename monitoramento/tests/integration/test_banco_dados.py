import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def test_duas_consultas_simultaneas_com_sessoes_distintas(
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    async def consultar() -> int:
        async with fabrica_sessao_teste() as sessao:
            resultado = await sessao.execute(text("SELECT 1"))
            return resultado.scalar_one()

    resultados = await asyncio.gather(consultar(), consultar())

    assert resultados == [1, 1]
