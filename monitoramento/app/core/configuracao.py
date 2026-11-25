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
    caminho_raiz: str = "/api"
    segredo_jwt: str
    minutos_expiracao_token: int = 60
    segredo_webhook: str
    tolerancia_timestamp_webhook_segundos: int = 300
    url_transportadora: str = "http://transportadora:8001"
    chave_api_transportadora: str
    timeout_transportadora_segundos: int = 3
    url_publica_webhook: str = "http://monitoramento:8000/webhooks/transportadora"
    intervalo_rotina_registro_segundos: int = 5
    max_tentativas_registro: int = 8
    base_backoff_registro_segundos: int = 5
    teto_backoff_registro_segundos: int = 60
    concorrencia_maxima_registro: int = 5
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
