from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.encomenda import Encomenda
from app.models.enums import StatusEncomenda


class RepositorioEncomenda:
    def __init__(self, sessao: AsyncSession) -> None:
        self._sessao = sessao

    async def obter_por_id(self, encomenda_id: int) -> Encomenda | None:
        resultado = await self._sessao.execute(
            select(Encomenda)
            .where(Encomenda.id == encomenda_id)
            .options(selectinload(Encomenda.historico), selectinload(Encomenda.usuario))
        )
        return resultado.scalar_one_or_none()

    async def obter_por_codigo_rastreio(self, codigo_rastreio: str) -> Encomenda | None:
        resultado = await self._sessao.execute(
            select(Encomenda).where(Encomenda.codigo_rastreio == codigo_rastreio)
        )
        return resultado.scalar_one_or_none()

    async def listar_por_usuario(
        self,
        usuario_id: int,
        grupo: str | None = None,
    ) -> list[Encomenda]:
        consulta = (
            select(Encomenda)
            .where(Encomenda.usuario_id == usuario_id)
            .options(selectinload(Encomenda.historico))
            .order_by(Encomenda.criado_em.desc())
        )
        if grupo is not None:
            consulta = consulta.where(
                Encomenda.status.in_(
                    status for status in StatusEncomenda if _grupo_do_status(status) == grupo
                )
            )
        resultado = await self._sessao.execute(consulta)
        return list(resultado.scalars().all())

    async def listar_todas(
        self,
        grupo: str | None = None,
        usuario_id: int | None = None,
    ) -> list[Encomenda]:
        consulta = (
            select(Encomenda)
            .options(selectinload(Encomenda.historico), selectinload(Encomenda.usuario))
            .order_by(Encomenda.criado_em.desc())
        )
        if grupo is not None:
            consulta = consulta.where(
                Encomenda.status.in_(
                    status for status in StatusEncomenda if _grupo_do_status(status) == grupo
                )
            )
        if usuario_id is not None:
            consulta = consulta.where(Encomenda.usuario_id == usuario_id)
        resultado = await self._sessao.execute(consulta)
        return list(resultado.scalars().all())

    async def criar(self, encomenda: Encomenda) -> Encomenda:
        self._sessao.add(encomenda)
        await self._sessao.flush()
        await self._sessao.refresh(encomenda)
        return encomenda

    async def obter_com_historico(self, encomenda_id: int) -> Encomenda | None:
        resultado = await self._sessao.execute(
            select(Encomenda)
            .where(Encomenda.id == encomenda_id)
            .options(selectinload(Encomenda.historico))
        )
        return resultado.scalar_one_or_none()

    async def atualizar_campos(
        self,
        encomenda: Encomenda,
        descricao: str | None,
        vendedor: str | None,
        agora: datetime,
    ) -> Encomenda:
        if descricao is not None:
            encomenda.descricao = descricao
        if vendedor is not None:
            encomenda.vendedor = vendedor
        encomenda.atualizado_em = agora
        await self._sessao.flush()
        await self._sessao.refresh(encomenda)
        return encomenda

    async def excluir(self, encomenda: Encomenda) -> None:
        await self._sessao.delete(encomenda)


def _grupo_do_status(status: StatusEncomenda) -> str:
    from app.services.maquina_de_estados import GRUPO_POR_STATUS

    return GRUPO_POR_STATUS[status]
