from pydantic import BaseModel

from app.models.enums import Papel


class TokenAcesso(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdministradorLer(BaseModel):
    email: str
    papel: Papel
