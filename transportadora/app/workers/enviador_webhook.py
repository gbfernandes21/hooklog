import logging
from dataclasses import dataclass
from datetime import datetime

import httpx

from app.core.assinador_hmac import assinar
from app.core.configuracao import Configuracao
from app.models.evento_webhook import EventoWebhook

logger = logging.getLogger(__name__)

STATUS_HTTP_FALHA_PERMANENTE = {401, 404, 409, 422}
STATUS_HTTP_REAGENDA = {408, 429}


@dataclass(frozen=True)
class ResultadoEnvio:
    enviado: bool
    falha_permanente: bool
    atraso_segundos: int | None
    status_http: int | None
    erro: str | None


class EnviadorWebhook:
    def __init__(
        self,
        cliente_http: httpx.AsyncClient,
        configuracao: Configuracao,
    ) -> None:
        self._cliente_http = cliente_http
        self._configuracao = configuracao

    async def enviar_evento(
        self,
        evento: EventoWebhook,
        agora: datetime,
    ) -> ResultadoEnvio:
        corpo_bruto = evento.corpo.encode("utf-8")
        carimbo_tempo = int(agora.timestamp())
        cabecalhos = assinar(
            self._configuracao.segredo_webhook,
            carimbo_tempo,
            corpo_bruto,
        )
        cabecalhos["Content-Type"] = "application/json"

        tentativa_numero = evento.total_tentativas + 1
        status_http: int | None = None
        erro: str | None = None

        try:
            resposta = await self._cliente_http.post(
                evento.remessa.url_callback,
                content=corpo_bruto,
                headers=cabecalhos,
                timeout=self._configuracao.timeout_envio_webhook_segundos,
            )
            status_http = resposta.status_code
        except httpx.TimeoutException:
            erro = "tempo esgotado"
            logger.warning(
                "Evento %s, tentativa %d: timeout ao enviar para %s",
                evento.id_evento,
                tentativa_numero,
                evento.remessa.url_callback,
            )
        except httpx.TransportError:
            erro = "conexao recusada"
            logger.warning(
                "Evento %s, tentativa %d: falha de conexao ao enviar para %s",
                evento.id_evento,
                tentativa_numero,
                evento.remessa.url_callback,
            )

        if status_http is not None and 200 <= status_http < 300:
            return ResultadoEnvio(
                enviado=True,
                falha_permanente=False,
                atraso_segundos=None,
                status_http=status_http,
                erro=None,
            )

        if status_http is not None and status_http in STATUS_HTTP_FALHA_PERMANENTE:
            return ResultadoEnvio(
                enviado=False,
                falha_permanente=True,
                atraso_segundos=None,
                status_http=status_http,
                erro=erro or f"resposta {status_http}",
            )

        if status_http is not None and status_http in STATUS_HTTP_REAGENDA:
            atraso = self._calcular_atraso(tentativa_numero)
            return ResultadoEnvio(
                enviado=False,
                falha_permanente=False,
                atraso_segundos=atraso,
                status_http=status_http,
                erro=erro or f"resposta {status_http}",
            )

        atraso = self._calcular_atraso(tentativa_numero)
        return ResultadoEnvio(
            enviado=False,
            falha_permanente=False,
            atraso_segundos=atraso,
            status_http=status_http,
            erro=erro or "falha de rede",
        )

    def _calcular_atraso(self, tentativa_numero: int) -> int:
        return self._configuracao.base_backoff_webhook_segundos * (2 ** (tentativa_numero - 1))
