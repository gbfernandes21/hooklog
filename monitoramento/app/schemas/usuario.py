import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import Papel

_PADRAO_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class UsuarioRegistro(BaseModel):
    email: str
    senha: str = Field(min_length=8)

    @field_validator("email")
    @classmethod
    def validar_email(cls, valor: str) -> str:
        valor_normalizado = valor.strip().lower()
        if not _PADRAO_EMAIL.match(valor_normalizado):
            raise ValueError("E-mail inválido")
        return valor_normalizado


class UsuarioLer(BaseModel):
    id: int
    email: str
    papel: Papel
    criado_em: datetime


class UsuarioAutenticadoLer(BaseModel):
    id: int | None
    email: str
    papel: Papel


class TokenAcesso(BaseModel):
    access_token: str
    token_type: str = "bearer"
