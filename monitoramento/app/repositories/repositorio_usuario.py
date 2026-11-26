from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usuario import Usuario


class RepositorioUsuario:
    def __init__(self, sessao: AsyncSession) -> None:
        self._sessao = sessao

    async def obter_por_email(self, email: str) -> Usuario | None:
        resultado = await self._sessao.execute(select(Usuario).where(Usuario.email == email))
        return resultado.scalar_one_or_none()

    async def obter_por_id(self, usuario_id: int) -> Usuario | None:
        resultado = await self._sessao.execute(select(Usuario).where(Usuario.id == usuario_id))
        return resultado.scalar_one_or_none()

    async def criar(self, usuario: Usuario) -> Usuario:
        self._sessao.add(usuario)
        await self._sessao.flush()
        return usuario
