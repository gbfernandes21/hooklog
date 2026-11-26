from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.erros import ErroDeDominio
from app.models.encomenda import Encomenda
from app.models.enums import StatusEncomenda
from app.models.historico_status import HistoricoStatus
from app.repositories.repositorio_encomenda import RepositorioEncomenda


class ServicoEncomenda:
    def __init__(self, sessao: AsyncSession) -> None:
        self._sessao = sessao
        self._repositorio = RepositorioEncomenda(sessao)

    async def criar(
        self,
        usuario_id: int,
        codigo_rastreio: str,
        descricao: str,
        vendedor: str,
        agora: datetime,
    ) -> Encomenda:
        encomenda = Encomenda(
            usuario_id=usuario_id,
            codigo_rastreio=codigo_rastreio,
            descricao=descricao,
            vendedor=vendedor,
            status=StatusEncomenda.REGISTRO_PENDENTE.value,
            tentativas_registro=0,
            proxima_tentativa_em=agora,
            criado_em=agora,
            atualizado_em=agora,
        )
        try:
            encomenda = await self._repositorio.criar(encomenda)
        except IntegrityError as erro:
            await self._sessao.rollback()
            raise ErroDeDominio(
                "Código de rastreio já cadastrado", "CODIGO_RASTREIO_DUPLICADO", 409
            ) from erro

        historico = HistoricoStatus(
            encomenda_id=encomenda.id,
            status_anterior=None,
            status_novo=encomenda.status,
            ocorrido_em=agora,
            registrado_em=agora,
        )
        self._sessao.add(historico)
        await self._sessao.commit()
        encomenda = await self._repositorio.obter_com_historico(encomenda.id)
        return encomenda

    async def listar_por_usuario(
        self,
        usuario_id: int,
        grupo: str | None,
    ) -> list[Encomenda]:
        return await self._repositorio.listar_por_usuario(usuario_id, grupo)

    async def obter_por_id_para_usuario(
        self,
        usuario_id: int,
        encomenda_id: int,
    ) -> Encomenda:
        encomenda = await self._repositorio.obter_por_id(encomenda_id)
        if encomenda is None or encomenda.usuario_id != usuario_id:
            raise ErroDeDominio("Encomenda não encontrada", "ENCOMENDA_NAO_ENCONTRADA", 404)
        return encomenda

    async def atualizar(
        self,
        usuario_id: int,
        encomenda_id: int,
        descricao: str | None,
        vendedor: str | None,
        agora: datetime,
    ) -> Encomenda:
        encomenda = await self.obter_por_id_para_usuario(usuario_id, encomenda_id)
        encomenda = await self._repositorio.atualizar_campos(encomenda, descricao, vendedor, agora)
        await self._sessao.commit()
        encomenda = await self._repositorio.obter_com_historico(encomenda.id)
        return encomenda

    async def excluir(
        self,
        usuario_id: int,
        encomenda_id: int,
    ) -> None:
        encomenda = await self.obter_por_id_para_usuario(usuario_id, encomenda_id)
        await self._repositorio.excluir(encomenda)
        await self._sessao.commit()

    async def listar_todas(
        self,
        grupo: str | None,
        usuario_id: int | None,
    ) -> list[Encomenda]:
        return await self._repositorio.listar_todas(grupo, usuario_id)

    async def obter_por_id_para_admin(
        self,
        encomenda_id: int,
    ) -> Encomenda:
        encomenda = await self._repositorio.obter_por_id(encomenda_id)
        if encomenda is None:
            raise ErroDeDominio("Encomenda não encontrada", "ENCOMENDA_NAO_ENCONTRADA", 404)
        return encomenda
