import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.erros import ErroDeDominio
from app.models.enums import EstadoEnvio
from app.models.evento_webhook import EventoWebhook
from app.repositories.repositorio_evento_webhook import RepositorioEventoWebhook
from app.schemas.logs_webhook import (
    EventoWebhookLer,
    FiltroLogsWebhook,
    TentativaWebhookLer,
)

logger = logging.getLogger(__name__)


class ServicoLogsWebhook:
    def __init__(self, sessao: AsyncSession) -> None:
        self._sessao = sessao
        self._repositorio = RepositorioEventoWebhook(sessao)

    async def listar(
        self,
        codigo_rastreio: str | None = None,
        estado: str | None = None,
    ) -> list[EventoWebhookLer]:
        filtro = FiltroLogsWebhook(codigo_rastreio=codigo_rastreio, estado=estado)
        eventos = await self._repositorio.listar_para_log(
            codigo_rastreio=filtro.codigo_rastreio,
            estado=filtro.estado,
        )
        return [self._para_ler(evento) for evento in eventos]

    async def reenviar(
        self,
        evento_id: int,
        agora: datetime,
    ) -> EventoWebhookLer:
        evento = await self._repositorio.obter_por_id_com_tentativas(evento_id)
        if evento is None:
            await self._sessao.rollback()
            raise ErroDeDominio(
                "Evento de webhook não encontrado",
                "EVENTO_WEBHOOK_NAO_ENCONTRADO",
                404,
            )

        await self._repositorio.redefinir_para_pendente(evento, agora)
        await self._sessao.commit()

        logger.info(
            "Evento %s reenviado manualmente para a remessa %s",
            evento.id_evento,
            evento.remessa.codigo_rastreio,
        )

        return self._para_ler(evento)

    def _para_ler(self, evento: EventoWebhook) -> EventoWebhookLer:
        return EventoWebhookLer(
            id=evento.id,
            id_evento=evento.id_evento,
            tipo_evento=evento.tipo_evento,
            codigo_rastreio=evento.remessa.codigo_rastreio,
            estado=EstadoEnvio(evento.estado),
            total_tentativas=evento.total_tentativas,
            ultimo_status_http=evento.ultimo_status_http,
            ultimo_erro=evento.ultimo_erro,
            criado_em=evento.criado_em,
            enviado_em=evento.enviado_em,
            historico_tentativas=[
                TentativaWebhookLer(
                    numero=tentativa.numero,
                    status_http=tentativa.status_http,
                    erro=tentativa.erro,
                    duracao_ms=tentativa.duracao_ms,
                    tentou_em=tentativa.tentou_em,
                )
                for tentativa in evento.tentativas
            ],
        )
