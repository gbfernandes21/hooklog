import pytest
from pydantic import ValidationError

from app.core.configuracao import Configuracao


def test_configuracao_sem_admin_email_levanta_erro_validacao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ADMIN_EMAIL", raising=False)

    with pytest.raises(ValidationError):
        Configuracao(_env_file=None)


def test_configuracao_sem_admin_senha_levanta_erro_validacao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ADMIN_SENHA", raising=False)

    with pytest.raises(ValidationError):
        Configuracao(_env_file=None)


def test_configuracao_com_email_invalido_levanta_erro_validacao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ADMIN_EMAIL", "nao-e-um-email")

    with pytest.raises(ValidationError):
        Configuracao(_env_file=None)


def test_configuracao_com_senha_de_7_caracteres_levanta_erro_validacao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ADMIN_SENHA", "1234567")

    with pytest.raises(ValidationError):
        Configuracao(_env_file=None)


def test_configuracao_valida_carrega_valores_do_ambiente() -> None:
    configuracao = Configuracao(_env_file=None)

    assert configuracao.admin_email == "admin@hooklog.test"
    assert configuracao.admin_senha == "senha-admin-123"
    assert configuracao.caminho_raiz == "/api"
    assert configuracao.tamanho_pool_banco == 10
