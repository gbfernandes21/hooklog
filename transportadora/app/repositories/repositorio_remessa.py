from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.remessa import Remessa


class RepositorioRemessa:
    def __init__(self, sessao: AsyncSession) -> None:
        self._sessao = sessao

    async def obter_por_codigo(self, codigo_rastreio: str) -> Remessa | None:
        resultado = await self._sessao.execute(
            select(Remessa).where(Remessa.codigo_rastreio == codigo_rastreio)
        )
        return resultado.scalar_one_or_none()

    async def obter_por_codigo_com_bloqueio(self, codigo_rastreio: str) -> Remessa | None:
        resultado = await self._sessao.execute(
            select(Remessa).where(Remessa.codigo_rastreio == codigo_rastreio).with_for_update()
        )
        return resultado.scalar_one_or_none()

    async def listar(self) -> list[Remessa]:
        resultado = await self._sessao.execute(
            select(Remessa).order_by(Remessa.criado_em.desc(), Remessa.id.desc())
        )
        return list(resultado.scalars().all())

    async def criar(self, remessa: Remessa) -> Remessa:
        self._sessao.add(remessa)
        await self._sessao.flush()
        return remessa
