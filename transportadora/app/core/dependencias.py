import secrets
from typing import Annotated

from fastapi import Depends
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer

from app.core.configuracao import Configuracao, obter_configuracao
from app.core.erros import ErroDeDominio
from app.core.seguranca import CredencialAutenticada, decodificar_token_acesso
from app.models.enums import Papel

esquema_oauth2 = OAuth2PasswordBearer(tokenUrl="autenticacao/login", auto_error=False)
esquema_chave_api = APIKeyHeader(name="X-Chave-Api", auto_error=False)


async def obter_configuracao_atual() -> Configuracao:
    return obter_configuracao()


def _chave_api_confere(chave_api: str, configuracao: Configuracao) -> bool:
    return secrets.compare_digest(chave_api, configuracao.chave_api_servico)


async def exigir_admin(
    token: Annotated[str | None, Depends(esquema_oauth2)],
    chave_api: Annotated[str | None, Depends(esquema_chave_api)],
    configuracao: Annotated[Configuracao, Depends(obter_configuracao_atual)],
) -> CredencialAutenticada:
    if token is None:
        if chave_api is not None and _chave_api_confere(chave_api, configuracao):
            raise ErroDeDominio("Permissão insuficiente", "PERMISSAO_INSUFICIENTE", 403)
        if chave_api is not None:
            raise ErroDeDominio("Chave de API inválida", "CHAVE_API_INVALIDA", 401)
        raise ErroDeDominio("Token inválido", "TOKEN_INVALIDO", 401)

    payload = decodificar_token_acesso(token)
    if payload["papel"] != Papel.ADMIN.value:
        raise ErroDeDominio("Permissão insuficiente", "PERMISSAO_INSUFICIENTE", 403)

    return CredencialAutenticada(papel=Papel.ADMIN)


async def exigir_chave_servico(
    token: Annotated[str | None, Depends(esquema_oauth2)],
    chave_api: Annotated[str | None, Depends(esquema_chave_api)],
    configuracao: Annotated[Configuracao, Depends(obter_configuracao_atual)],
) -> None:
    if chave_api is not None:
        if _chave_api_confere(chave_api, configuracao):
            return
        raise ErroDeDominio("Chave de API inválida", "CHAVE_API_INVALIDA", 401)

    if token is not None:
        decodificar_token_acesso(token)
        raise ErroDeDominio("Permissão insuficiente", "PERMISSAO_INSUFICIENTE", 403)

    raise ErroDeDominio("Chave de API inválida", "CHAVE_API_INVALIDA", 401)
