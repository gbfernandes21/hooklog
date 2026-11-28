from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from app.models.enums import EstadoEnvio
from app.models.evento_webhook import EventoWebhook
from app.models.remessa import Remessa
from app.models.tentativa_webhook import TentativaWebhook


class RepositorioEventoWebhook:
    def __init__(self, sessao: AsyncSession) -> None:
        self._sessao = sessao

    async def criar(self, evento: EventoWebhook) -> EventoWebhook:
        self._sessao.add(evento)
        await self._sessao.flush()
        return evento

    async def listar_pendentes_elegiveis(
        self,
        agora: datetime,
        limite: int = 20,
    ) -> list[EventoWebhook]:
        outro = aliased(EventoWebhook)
        evento_mais_antigo = (
            select(outro.id)
            .where(
                outro.remessa_id == EventoWebhook.remessa_id,
                outro.estado == "PENDENTE",
                outro.id < EventoWebhook.id,
            )
            .correlate_except(outro)
        )
        resultado = await self._sessao.execute(
            select(EventoWebhook)
            .options(selectinload(EventoWebhook.remessa))
            .where(
                EventoWebhook.estado == "PENDENTE",
                EventoWebhook.proxima_tentativa_em <= agora,
                ~evento_mais_antigo.exists(),
            )
            .order_by(EventoWebhook.id)
            .limit(limite)
        )
        return list(resultado.scalars().all())

    async def criar_tentativa(
        self,
        evento_webhook_id: int,
        numero: int,
        status_http: int | None,
        erro: str | None,
        duracao_ms: int,
        tentou_em: datetime,
    ) -> TentativaWebhook:
        tentativa = TentativaWebhook(
            evento_webhook_id=evento_webhook_id,
            numero=numero,
            status_http=status_http,
            erro=erro,
            duracao_ms=duracao_ms,
            tentou_em=tentou_em,
        )
        self._sessao.add(tentativa)
        await self._sessao.flush()
        return tentativa

    async def marcar_enviado(
        self,
        evento: EventoWebhook,
        enviado_em: datetime,
        total_tentativas: int,
        ultimo_status_http: int | None,
        ultimo_erro: str | None = None,
    ) -> None:
        evento.estado = "ENVIADO"
        evento.enviado_em = enviado_em
        evento.total_tentativas = total_tentativas
        evento.ultimo_status_http = ultimo_status_http
        evento.ultimo_erro = ultimo_erro
        await self._sessao.flush()

    async def marcar_falha_definitiva(
        self,
        evento: EventoWebhook,
        total_tentativas: int,
        proxima_tentativa_em: datetime,
        ultimo_status_http: int | None,
        ultimo_erro: str | None,
    ) -> None:
        evento.estado = "FALHA"
        evento.total_tentativas = total_tentativas
        evento.proxima_tentativa_em = proxima_tentativa_em
        evento.ultimo_status_http = ultimo_status_http
        evento.ultimo_erro = ultimo_erro
        await self._sessao.flush()

    async def registrar_reagendamento(
        self,
        evento: EventoWebhook,
        total_tentativas: int,
        proxima_tentativa_em: datetime,
        ultimo_status_http: int | None,
        ultimo_erro: str | None,
    ) -> None:
        evento.total_tentativas = total_tentativas
        evento.proxima_tentativa_em = proxima_tentativa_em
        evento.ultimo_status_http = ultimo_status_http
        evento.ultimo_erro = ultimo_erro
        await self._sessao.flush()

    async def obter_por_id_com_tentativas(
        self,
        evento_id: int,
    ) -> EventoWebhook | None:
        resultado = await self._sessao.execute(
            select(EventoWebhook)
            .options(
                selectinload(EventoWebhook.tentativas),
                selectinload(EventoWebhook.remessa),
            )
            .where(EventoWebhook.id == evento_id)
        )
        return resultado.scalars().first()

    async def listar_para_log(
        self,
        codigo_rastreio: str | None = None,
        estado: str | None = None,
    ) -> list[EventoWebhook]:
        consulta = (
            select(EventoWebhook)
            .join(Remessa, Remessa.id == EventoWebhook.remessa_id)
            .options(
                selectinload(EventoWebhook.tentativas),
                selectinload(EventoWebhook.remessa),
            )
            .order_by(EventoWebhook.id.desc())
        )
        if codigo_rastreio is not None:
            consulta = consulta.where(Remessa.codigo_rastreio == codigo_rastreio)
        if estado is not None:
            consulta = consulta.where(EventoWebhook.estado == estado)
        resultado = await self._sessao.execute(consulta)
        return list(resultado.scalars().all())

    async def redefinir_para_pendente(
        self,
        evento: EventoWebhook,
        agora: datetime,
    ) -> None:
        evento.estado = EstadoEnvio.PENDENTE.value
        evento.total_tentativas = 0
        evento.proxima_tentativa_em = agora
        evento.ultimo_status_http = None
        evento.ultimo_erro = None
        await self._sessao.flush()
