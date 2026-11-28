import traceback
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.configuracao import Configuracao, obter_configuracao


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


def test_obter_configuracao_nao_expoe_admin_senha_na_mensagem(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    senha = "senha-secreta-123"
    # .env de teste sem ADMIN_EMAIL (simula arquivo mal configurado, como no cenario 9)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "URL_BANCO=postgresql+asyncpg://u:p@localhost:5433/db\n"
        "SEGREDO_JWT=um-segredo-com-pelo-menos-32-bytes\n"
        "SEGREDO_WEBHOOK=segredo-webhook-teste\n"
        "CHAVE_API_TRANSPORTADORA=chave-api-teste\n"
        "CAMINHO_RAIZ=/api\n"
        "MINUTOS_EXPIRACAO_TOKEN=60\n"
        "TOLERANCIA_TIMESTAMP_WEBHOOK_SEGUNDOS=300\n"
        "TAMANHO_POOL_BANCO=10\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ADMIN_SENHA", senha)
    monkeypatch.delenv("ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("SEGREDO_JWT", raising=False)
    monkeypatch.setitem(Configuracao.model_config, "env_file", env_file)
    obter_configuracao.cache_clear()

    with pytest.raises(SystemExit) as excinfo:
        obter_configuracao()

    mensagem = str(excinfo.value)
    assert senha not in mensagem
    assert senha not in "".join(traceback.format_exception(excinfo.value))
    obter_configuracao.cache_clear()
