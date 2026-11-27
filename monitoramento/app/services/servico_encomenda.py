from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.cliente_transportadora import (
    ClienteTransportadora,
    ErroPermanente,
    ErroTransitorio,
)
from app.core.configuracao import Configuracao
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

    async def listar_pendentes_para_registro(
        self,
        agora: datetime,
        limite: int = 20,
    ) -> list[Encomenda]:
        return await self._repositorio.listar_pendentes_para_registro(agora, limite)

    async def obter_pendente_para_registro(
        self,
        encomenda_id: int,
        agora: datetime,
    ) -> Encomenda | None:
        return await self._repositorio.obter_pendente_para_registro(encomenda_id, agora)

    async def registrar_na_transportadora(
        self,
        encomenda: Encomenda,
        cliente: ClienteTransportadora,
        agora: datetime,
        configuracao: Configuracao,
    ) -> Encomenda:
        await self._sessao.commit()

        try:
            await cliente.registrar_remessa(
                codigo_rastreio=encomenda.codigo_rastreio,
                vendedor=encomenda.vendedor,
                url_callback=configuracao.url_publica_webhook,
            )
        except ErroTransitorio as erro:
            self._aplicar_falha_transitoria(encomenda, str(erro), agora, configuracao)
        except ErroPermanente as erro:
            self._marcar_falha_no_registro(encomenda, str(erro), agora)
        else:
            self._aplicar_sucesso_registro(encomenda, agora)

        await self._sessao.commit()
        return await self._repositorio.obter_com_historico(encomenda.id)

    async def reiniciar_registro(
        self,
        usuario_id: int,
        encomenda_id: int,
        agora: datetime,
    ) -> Encomenda:
        encomenda = await self.obter_por_id_para_usuario(usuario_id, encomenda_id)
        if encomenda.status != StatusEncomenda.FALHA_NO_REGISTRO.value:
            raise ErroDeDominio(
                "Encomenda não está em falha no registro",
                "ESTADO_INVALIDO",
                409,
            )

        status_anterior = encomenda.status
        encomenda.status = StatusEncomenda.REGISTRO_PENDENTE.value
        encomenda.tentativas_registro = 0
        encomenda.proxima_tentativa_em = agora
        encomenda.ultimo_erro_registro = None
        encomenda.atualizado_em = agora
        self._adicionar_historico(encomenda, status_anterior, encomenda.status, agora)

        await self._sessao.commit()
        return await self._repositorio.obter_com_historico(encomenda.id)

    def _aplicar_sucesso_registro(self, encomenda: Encomenda, agora: datetime) -> None:
        status_anterior = encomenda.status
        encomenda.status = StatusEncomenda.AGUARDANDO_ENVIO.value
        encomenda.tentativas_registro = 0
        encomenda.proxima_tentativa_em = None
        encomenda.ultimo_erro_registro = None
        encomenda.atualizado_em = agora
        if status_anterior != encomenda.status:
            self._adicionar_historico(encomenda, status_anterior, encomenda.status, agora)

    def _aplicar_falha_transitoria(
        self,
        encomenda: Encomenda,
        mensagem: str,
        agora: datetime,
        configuracao: Configuracao,
    ) -> None:
        encomenda.tentativas_registro += 1
        encomenda.ultimo_erro_registro = mensagem
        encomenda.atualizado_em = agora

        if encomenda.tentativas_registro >= configuracao.max_tentativas_registro:
            self._marcar_falha_no_registro(encomenda, mensagem, agora)
            return

        atraso = min(
            configuracao.base_backoff_registro_segundos
            * (2 ** (encomenda.tentativas_registro - 1)),
            configuracao.teto_backoff_registro_segundos,
        )
        encomenda.proxima_tentativa_em = agora + timedelta(seconds=atraso)

    def _marcar_falha_no_registro(
        self,
        encomenda: Encomenda,
        mensagem: str,
        agora: datetime,
    ) -> None:
        status_anterior = encomenda.status
        encomenda.status = StatusEncomenda.FALHA_NO_REGISTRO.value
        encomenda.proxima_tentativa_em = None
        encomenda.ultimo_erro_registro = mensagem
        encomenda.atualizado_em = agora
        if status_anterior != encomenda.status:
            self._adicionar_historico(encomenda, status_anterior, encomenda.status, agora)

    def _adicionar_historico(
        self,
        encomenda: Encomenda,
        status_anterior: str,
        status_novo: str,
        agora: datetime,
    ) -> None:
        self._sessao.add(
            HistoricoStatus(
                encomenda_id=encomenda.id,
                status_anterior=status_anterior,
                status_novo=status_novo,
                ocorrido_em=agora,
                registrado_em=agora,
            )
        )

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
