import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt

from app.core.configuracao import Configuracao, obter_configuracao
from app.core.erros import ErroDeDominio
from app.models.enums import Papel

_ALGORITMO = "HS256"


@dataclass(frozen=True)
class CredencialAutenticada:
    papel: Papel


def autenticar_admin(email: str, senha: str, configuracao: Configuracao) -> bool:
    email_normalizado = email.strip().lower()
    email_confere = secrets.compare_digest(email_normalizado, configuracao.admin_email)
    senha_confere = secrets.compare_digest(senha, configuracao.admin_senha)
    return email_confere and senha_confere


def criar_token_acesso(sub: str | int, papel: Papel) -> str:
    configuracao = obter_configuracao()
    agora = datetime.now(UTC)
    payload = {
        "sub": str(sub),
        "papel": papel.value,
        "iat": agora,
        "exp": agora + timedelta(minutes=configuracao.minutos_expiracao_token),
    }
    return jwt.encode(payload, configuracao.segredo_jwt, algorithm=_ALGORITMO)


def decodificar_token_acesso(token: str) -> dict:
    configuracao = obter_configuracao()
    try:
        payload = jwt.decode(token, configuracao.segredo_jwt, algorithms=[_ALGORITMO])
    except jwt.ExpiredSignatureError as erro:
        raise ErroDeDominio("Token expirado", "TOKEN_EXPIRADO", 401) from erro
    except jwt.InvalidTokenError as erro:
        raise ErroDeDominio("Token inválido", "TOKEN_INVALIDO", 401) from erro

    sub = payload.get("sub")
    papel = payload.get("papel")
    papeis_validos = {membro.value for membro in Papel}
    if not isinstance(sub, str) or not sub or papel not in papeis_validos:
        raise ErroDeDominio("Token inválido", "TOKEN_INVALIDO", 401)

    if papel == Papel.USER.value:
        try:
            int(sub)
        except ValueError as erro:
            raise ErroDeDominio("Token inválido", "TOKEN_INVALIDO", 401) from erro
    elif sub != "admin":
        raise ErroDeDominio("Token inválido", "TOKEN_INVALIDO", 401)

    return payload
