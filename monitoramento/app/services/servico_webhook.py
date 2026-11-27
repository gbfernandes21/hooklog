from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.erros import ErroDeDominio
from app.models.enums import StatusEncomenda
from app.models.evento_processado import EventoProcessado
from app.models.historico_status import HistoricoStatus
from app.repositories.repositorio_encomenda import RepositorioEncomenda
from app.schemas.webhook import EventoWebhook
from app.services.maquina_de_estados import pode_aplicar_evento


class ServicoWebhook:
    def __init__(self, sessao: AsyncSession) -> None:
        self._sessao = sessao
        self._repositorio = RepositorioEncomenda(sessao)

    async def aplicar_evento(self, evento: EventoWebhook, agora: datetime) -> str:
        encomenda = await self._repositorio.obter_por_codigo_rastreio_para_atualizar(
            evento.codigo_rastreio
        )
        if encomenda is None:
            raise ErroDeDominio("Encomenda não encontrada", "ENCOMENDA_NAO_ENCONTRADA", 404)

        ja_processado = await self._sessao.get(EventoProcessado, evento.id_evento)
        if ja_processado is not None:
            return "duplicado"

        status_atual = StatusEncomenda(encomenda.status)
        status_evento = StatusEncomenda(evento.status)
        if not pode_aplicar_evento(status_atual, status_evento):
            raise ErroDeDominio("Transição de status inválida", "TRANSICAO_INVALIDA", 409)

        status_anterior = encomenda.status
        encomenda.status = evento.status
        if evento.status == StatusEncomenda.ENTREGUE.value:
            encomenda.entregue_em = evento.entregue_em or agora
        encomenda.atualizado_em = agora

        self._sessao.add(EventoProcessado(id_evento=evento.id_evento, recebido_em=agora))
        self._sessao.add(
            HistoricoStatus(
                encomenda_id=encomenda.id,
                status_anterior=status_anterior,
                status_novo=encomenda.status,
                id_evento=evento.id_evento,
                ocorrido_em=evento.ocorrido_em,
                registrado_em=agora,
            )
        )

        try:
            await self._sessao.commit()
        except IntegrityError:
            await self._sessao.rollback()
            return "duplicado"

        return "aplicado"
