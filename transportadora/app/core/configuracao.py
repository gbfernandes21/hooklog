import re
from functools import lru_cache

from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PADRAO_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class Configuracao(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    admin_email: str
    admin_senha: str = Field(min_length=8)
    url_banco: str
    caminho_raiz: str = "/transportadora"
    segredo_jwt: str
    minutos_expiracao_token: int = 60
    chave_api_servico: str
    segredo_webhook: str
    max_tentativas_webhook: int = 5
    base_backoff_webhook_segundos: int = 1
    intervalo_rotina_webhook_segundos: int = 1
    timeout_envio_webhook_segundos: int = 5
    concorrencia_maxima_webhook: int = 5
    tamanho_pool_banco: int = 10

    @field_validator("admin_email")
    @classmethod
    def validar_admin_email(cls, valor: str) -> str:
        valor_limpo = valor.strip().lower()
        if not _PADRAO_EMAIL.match(valor_limpo):
            raise ValueError("ADMIN_EMAIL deve ser um e-mail válido")
        return valor_limpo


@lru_cache
def obter_configuracao() -> Configuracao:
    try:
        return Configuracao()
    except ValidationError as erro:
        raise SystemExit(
            "Configuração inválida. Defina ADMIN_EMAIL e ADMIN_SENHA (mínimo 8 "
            "caracteres) no arquivo .env, além das demais variáveis obrigatórias.\n"
            f"{erro}"
        ) from erro
