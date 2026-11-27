import httpx

from app.core.configuracao import Configuracao


class ErroRegistroTransportadora(Exception):
    """Falha ao registrar uma remessa na transportadora."""


class ErroTransitorio(ErroRegistroTransportadora):
    """Falha temporária: vale a pena tentar de novo mais tarde."""


class ErroPermanente(ErroRegistroTransportadora):
    """Falha de contrato ou configuração: repetir não resolve."""


class ClienteTransportadora:
    def __init__(self, cliente_http: httpx.AsyncClient, configuracao: Configuracao) -> None:
        self._cliente_http = cliente_http
        self._configuracao = configuracao

    async def registrar_remessa(
        self,
        codigo_rastreio: str,
        vendedor: str,
        url_callback: str,
    ) -> None:
        url = f"{self._configuracao.url_transportadora.rstrip('/')}/remessas"
        corpo = {
            "codigo_rastreio": codigo_rastreio,
            "vendedor": vendedor,
            "url_callback": url_callback,
        }
        try:
            resposta = await self._cliente_http.post(
                url,
                json=corpo,
                headers={"X-Chave-Api": self._configuracao.chave_api_transportadora},
            )
        except httpx.TimeoutException as erro:
            raise ErroTransitorio("Tempo esgotado ao registrar a remessa") from erro
        except httpx.TransportError as erro:
            raise ErroTransitorio("Falha de conexão com a transportadora") from erro

        if resposta.status_code in (200, 201):
            return

        if resposta.status_code in (408, 429) or resposta.status_code >= 500:
            raise ErroTransitorio(
                f"Transportadora respondeu {resposta.status_code} ao registrar a remessa"
            )

        raise ErroPermanente(
            f"Transportadora respondeu {resposta.status_code} ao registrar a remessa"
        )
