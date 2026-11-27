from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evento_webhook import EventoWebhook


class RepositorioEventoWebhook:
    def __init__(self, sessao: AsyncSession) -> None:
        self._sessao = sessao

    async def criar(self, evento: EventoWebhook) -> EventoWebhook:
        self._sessao.add(evento)
        await self._sessao.flush()
        return evento
