from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from app.core.configuracao import Configuracao, obter_configuracao
from app.core.erros import ErroDeDominio
from app.core.seguranca import UsuarioAutenticado, decodificar_token_acesso
from app.models.enums import Papel

esquema_oauth2 = OAuth2PasswordBearer(tokenUrl="autenticacao/login", auto_error=False)


async def obter_configuracao_atual() -> Configuracao:
    return obter_configuracao()


async def obter_usuario_atual(
    token: Annotated[str | None, Depends(esquema_oauth2)],
) -> UsuarioAutenticado:
    if token is None:
        raise ErroDeDominio("Token inválido", "TOKEN_INVALIDO", 401)

    payload = decodificar_token_acesso(token)
    papel = Papel(payload["papel"])
    if papel is Papel.ADMIN:
        return UsuarioAutenticado(id=None, papel=papel)

    return UsuarioAutenticado(id=int(payload["sub"]), papel=papel)


async def exigir_usuario(
    usuario: Annotated[UsuarioAutenticado, Depends(obter_usuario_atual)],
) -> UsuarioAutenticado:
    if usuario.papel is not Papel.USER:
        raise ErroDeDominio("Acesso negado", "ACESSO_NEGADO", 403)
    return usuario


async def exigir_admin(
    usuario: Annotated[UsuarioAutenticado, Depends(obter_usuario_atual)],
) -> UsuarioAutenticado:
    if usuario.papel is not Papel.ADMIN:
        raise ErroDeDominio("Acesso negado", "ACESSO_NEGADO", 403)
    return usuario
