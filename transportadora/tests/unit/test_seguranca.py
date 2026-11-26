from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.configuracao import obter_configuracao
from app.core.erros import ErroDeDominio
from app.core.seguranca import (
    autenticar_admin,
    criar_token_acesso,
    decodificar_token_acesso,
)
from app.models.enums import Papel

ADMIN_EMAIL = "admin@hooklog.test"
ADMIN_SENHA = "senha-admin-123"


def _token_com_payload(payload: dict, chave: str | None = None) -> str:
    configuracao = obter_configuracao()
    return jwt.encode(
        payload,
        chave or configuracao.segredo_jwt,
        algorithm="HS256",
    )


def _payload_valido() -> dict:
    return {
        "sub": "admin",
        "papel": "ADMIN",
        "exp": datetime.now(UTC) + timedelta(minutes=5),
    }


def test_autenticar_admin_aceita_email_em_maiusculas() -> None:
    assert autenticar_admin("ADMIN@HOOKLOG.TEST", ADMIN_SENHA, obter_configuracao()) is True


def test_autenticar_admin_recusa_email_errado() -> None:
    assert autenticar_admin("outro@hooklog.test", ADMIN_SENHA, obter_configuracao()) is False


def test_autenticar_admin_recusa_senha_errada() -> None:
    assert autenticar_admin(ADMIN_EMAIL, "senha-errada", obter_configuracao()) is False


def test_criar_e_decodificar_token_acesso_do_admin() -> None:
    token = criar_token_acesso("admin", Papel.ADMIN)

    payload = decodificar_token_acesso(token)

    assert payload["sub"] == "admin"
    assert payload["papel"] == "ADMIN"
    assert "exp" in payload


def test_token_expirado_levanta_erro_de_dominio() -> None:
    payload = _payload_valido()
    payload["exp"] = datetime.now(UTC) - timedelta(minutes=1)

    with pytest.raises(ErroDeDominio) as excinfo:
        decodificar_token_acesso(_token_com_payload(payload))

    assert excinfo.value.codigo == "TOKEN_EXPIRADO"
    assert excinfo.value.status_code == 401


def test_token_adulterado_levanta_erro_de_dominio() -> None:
    token = criar_token_acesso("admin", Papel.ADMIN)
    sufixo_original = token[-2:]
    sufixo_novo = "aa" if sufixo_original != "aa" else "bb"
    token_adulterado = token[:-2] + sufixo_novo

    with pytest.raises(ErroDeDominio) as excinfo:
        decodificar_token_acesso(token_adulterado)

    assert excinfo.value.codigo == "TOKEN_INVALIDO"
    assert excinfo.value.status_code == 401


def test_token_sem_sub_levanta_erro_de_dominio() -> None:
    payload = _payload_valido()
    payload.pop("sub")

    with pytest.raises(ErroDeDominio) as excinfo:
        decodificar_token_acesso(_token_com_payload(payload))

    assert excinfo.value.codigo == "TOKEN_INVALIDO"
    assert excinfo.value.status_code == 401


def test_token_sem_papel_levanta_erro_de_dominio() -> None:
    payload = _payload_valido()
    payload.pop("papel")

    with pytest.raises(ErroDeDominio) as excinfo:
        decodificar_token_acesso(_token_com_payload(payload))

    assert excinfo.value.codigo == "TOKEN_INVALIDO"
    assert excinfo.value.status_code == 401


def test_token_com_outra_chave_levanta_erro_de_dominio() -> None:
    token = _token_com_payload(_payload_valido(), chave="segredo-jwt-do-monitoramento-com-32-bytes")

    with pytest.raises(ErroDeDominio) as excinfo:
        decodificar_token_acesso(token)

    assert excinfo.value.codigo == "TOKEN_INVALIDO"
    assert excinfo.value.status_code == 401


def test_token_de_admin_com_sub_diferente_de_admin_levanta_erro_de_dominio() -> None:
    payload = _payload_valido()
    payload["sub"] = "123"

    with pytest.raises(ErroDeDominio) as excinfo:
        decodificar_token_acesso(_token_com_payload(payload))

    assert excinfo.value.codigo == "TOKEN_INVALIDO"
    assert excinfo.value.status_code == 401
