from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.configuracao import obter_configuracao
from app.core.erros import ErroDeDominio
from app.core.seguranca import (
    autenticar_admin,
    criar_token_acesso,
    decodificar_token_acesso,
    gerar_hash_senha,
    verificar_senha,
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
        "sub": "1",
        "papel": "USER",
        "exp": datetime.now(UTC) + timedelta(minutes=5),
    }


def test_gerar_hash_senha_nao_armazena_a_senha_em_texto() -> None:
    hash_senha = gerar_hash_senha("minhasenha123")

    assert hash_senha != "minhasenha123"
    assert hash_senha.startswith("$argon2")


def test_verificar_senha_correta_retorna_true() -> None:
    hash_senha = gerar_hash_senha("minhasenha123")

    assert verificar_senha("minhasenha123", hash_senha) is True


def test_verificar_senha_errada_retorna_false() -> None:
    hash_senha = gerar_hash_senha("minhasenha123")

    assert verificar_senha("outrasenha", hash_senha) is False


def test_autenticar_admin_aceita_email_em_maiusculas() -> None:
    assert autenticar_admin("ADMIN@HOOKLOG.TEST", ADMIN_SENHA, obter_configuracao()) is True


def test_autenticar_admin_recusa_email_errado() -> None:
    assert autenticar_admin("outro@hooklog.test", ADMIN_SENHA, obter_configuracao()) is False


def test_autenticar_admin_recusa_senha_errada() -> None:
    assert autenticar_admin(ADMIN_EMAIL, "senha-errada", obter_configuracao()) is False


def test_criar_e_decodificar_token_acesso_com_sub_e_papel() -> None:
    token = criar_token_acesso("1", Papel.USER)

    payload = decodificar_token_acesso(token)

    assert payload["sub"] == "1"
    assert payload["papel"] == "USER"
    assert "exp" in payload


def test_token_expirado_levanta_erro_de_dominio() -> None:
    token = _token_com_payload(
        {
            "sub": "1",
            "papel": "USER",
            "exp": datetime.now(UTC) - timedelta(minutes=1),
        }
    )

    with pytest.raises(ErroDeDominio) as excinfo:
        decodificar_token_acesso(token)

    assert excinfo.value.codigo == "TOKEN_EXPIRADO"
    assert excinfo.value.status_code == 401


def test_token_adulterado_levanta_erro_de_dominio() -> None:
    token = criar_token_acesso("1", Papel.USER)
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
    token = _token_com_payload(
        _payload_valido(), chave="outra-chave-qualquer-com-mais-de-32-bytes"
    )

    with pytest.raises(ErroDeDominio) as excinfo:
        decodificar_token_acesso(token)

    assert excinfo.value.codigo == "TOKEN_INVALIDO"
    assert excinfo.value.status_code == 401


def test_token_de_user_com_sub_nao_numerico_levanta_erro_de_dominio() -> None:
    payload = _payload_valido()
    payload["sub"] = "nao-e-numero"

    with pytest.raises(ErroDeDominio) as excinfo:
        decodificar_token_acesso(_token_com_payload(payload))

    assert excinfo.value.codigo == "TOKEN_INVALIDO"
    assert excinfo.value.status_code == 401


def test_token_de_admin_com_sub_diferente_de_admin_levanta_erro_de_dominio() -> None:
    payload = _payload_valido()
    payload["sub"] = "123"
    payload["papel"] = "ADMIN"

    with pytest.raises(ErroDeDominio) as excinfo:
        decodificar_token_acesso(_token_com_payload(payload))

    assert excinfo.value.codigo == "TOKEN_INVALIDO"
    assert excinfo.value.status_code == 401
