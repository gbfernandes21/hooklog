import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.erros import ErroDeDominio
from app.models.enums import EstadoEnvio, StatusRemessa
from app.models.evento_webhook import EventoWebhook
from app.models.remessa import Remessa
from app.repositories.repositorio_evento_webhook import RepositorioEventoWebhook
from app.repositories.repositorio_remessa import RepositorioRemessa
from app.services.maquina_de_estados import proximo_status

logger = logging.getLogger(__name__)

TIPO_STATUS_ALTERADO = "remessa.status_alterado"
TIPO_ENTREGUE = "remessa.entregue"


@dataclass(frozen=True)
class ResultadoCriacaoRemessa:
    remessa: Remessa
    criada: bool


class ServicoRemessa:
    def __init__(self, sessao: AsyncSession) -> None:
        self._sessao = sessao
        self._repositorio = RepositorioRemessa(sessao)
        self._repositorio_evento = RepositorioEventoWebhook(sessao)

    async def criar(
        self,
        codigo_rastreio: str,
        vendedor: str,
        url_callback: str,
        agora: datetime,
    ) -> ResultadoCriacaoRemessa:
        remessa = Remessa(
            codigo_rastreio=codigo_rastreio,
            vendedor=vendedor,
            status=StatusRemessa.AGUARDANDO_ENVIO.value,
            url_callback=url_callback,
            criado_em=agora,
            atualizado_em=agora,
        )
        try:
            await self._repositorio.criar(remessa)
            await self._sessao.commit()
        except IntegrityError:
            await self._sessao.rollback()
            existente = await self._repositorio.obter_por_codigo(codigo_rastreio)
            if existente is None:
                raise
            return ResultadoCriacaoRemessa(remessa=existente, criada=False)

        return ResultadoCriacaoRemessa(remessa=remessa, criada=True)

    async def obter_por_codigo(self, codigo_rastreio: str) -> Remessa:
        remessa = await self._repositorio.obter_por_codigo(codigo_rastreio)
        if remessa is None:
            raise ErroDeDominio("Remessa não encontrada", "REMESSA_NAO_ENCONTRADA", 404)
        return remessa

    async def listar(self) -> list[Remessa]:
        return await self._repositorio.listar()

    async def mudar_status(
        self,
        codigo_rastreio: str,
        novo_status: StatusRemessa,
        agora: datetime,
    ) -> Remessa:
        remessa = await self._repositorio.obter_por_codigo_com_bloqueio(codigo_rastreio)
        if remessa is None:
            await self._sessao.rollback()
            raise ErroDeDominio("Remessa não encontrada", "REMESSA_NAO_ENCONTRADA", 404)

        status_atual = StatusRemessa(remessa.status)
        if proximo_status(status_atual) != novo_status:
            await self._sessao.rollback()
            raise ErroDeDominio("Transição de status inválida", "TRANSICAO_INVALIDA", 409)

        try:
            remessa.status = novo_status.value
            remessa.atualizado_em = agora
            await self._criar_evento_status_alterado(remessa, agora)
            await self._sessao.commit()
        except Exception:
            await self._sessao.rollback()
            raise

        return remessa

    async def entregar(
        self,
        codigo_rastreio: str,
        recebido_por: str | None,
        agora: datetime,
    ) -> Remessa:
        remessa = await self._repositorio.obter_por_codigo_com_bloqueio(codigo_rastreio)
        if remessa is None:
            await self._sessao.rollback()
            raise ErroDeDominio("Remessa não encontrada", "REMESSA_NAO_ENCONTRADA", 404)

        if StatusRemessa(remessa.status) != StatusRemessa.SAIU_PARA_ENTREGA:
            await self._sessao.rollback()
            raise ErroDeDominio("Transição de status inválida", "TRANSICAO_INVALIDA", 409)

        try:
            remessa.status = StatusRemessa.ENTREGUE.value
            remessa.entregue_em = agora
            remessa.recebido_por = recebido_por
            remessa.atualizado_em = agora
            await self._criar_evento_entregue(remessa, recebido_por, agora)
            await self._sessao.commit()
        except Exception:
            await self._sessao.rollback()
            raise

        return remessa

    async def _criar_evento_status_alterado(
        self,
        remessa: Remessa,
        agora: datetime,
    ) -> None:
        id_evento = str(uuid4())
        corpo: dict[str, str] = {
            "id_evento": id_evento,
            "tipo_evento": TIPO_STATUS_ALTERADO,
            "codigo_rastreio": remessa.codigo_rastreio,
            "status": remessa.status,
            "vendedor": remessa.vendedor,
            "ocorrido_em": _para_iso_utc(agora),
        }
        await self._registrar_evento(
            remessa=remessa,
            id_evento=id_evento,
            tipo_evento=TIPO_STATUS_ALTERADO,
            corpo=corpo,
            agora=agora,
        )

    async def _criar_evento_entregue(
        self,
        remessa: Remessa,
        recebido_por: str | None,
        agora: datetime,
    ) -> None:
        id_evento = str(uuid4())
        corpo: dict[str, str] = {
            "id_evento": id_evento,
            "tipo_evento": TIPO_ENTREGUE,
            "codigo_rastreio": remessa.codigo_rastreio,
            "status": StatusRemessa.ENTREGUE.value,
            "vendedor": remessa.vendedor,
            "ocorrido_em": _para_iso_utc(agora),
            "entregue_em": _para_iso_utc(agora),
        }
        if recebido_por is not None:
            corpo["recebido_por"] = recebido_por
        await self._registrar_evento(
            remessa=remessa,
            id_evento=id_evento,
            tipo_evento=TIPO_ENTREGUE,
            corpo=corpo,
            agora=agora,
        )

    async def _registrar_evento(
        self,
        remessa: Remessa,
        id_evento: str,
        tipo_evento: str,
        corpo: dict[str, str],
        agora: datetime,
    ) -> None:
        evento = EventoWebhook(
            remessa_id=remessa.id,
            id_evento=id_evento,
            tipo_evento=tipo_evento,
            corpo=json.dumps(corpo, ensure_ascii=False, separators=(",", ":")),
            estado=EstadoEnvio.PENDENTE.value,
            total_tentativas=0,
            proxima_tentativa_em=agora,
            criado_em=agora,
        )
        await self._repositorio_evento.criar(evento)
        logger.info(
            "Evento %s (%s) gerado para a remessa %s",
            id_evento,
            tipo_evento,
            remessa.codigo_rastreio,
        )


def _para_iso_utc(momento: datetime) -> str:
    return momento.astimezone(UTC).isoformat().replace("+00:00", "Z")
