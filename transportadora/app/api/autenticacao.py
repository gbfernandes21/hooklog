from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from app.core.configuracao import Configuracao
from app.core.dependencias import exigir_admin, obter_configuracao_atual
from app.core.seguranca import CredencialAutenticada
from app.schemas.autenticacao import AdministradorLer, TokenAcesso
from app.services.servico_autenticacao import ServicoAutenticacao

roteador = APIRouter(prefix="/autenticacao", tags=["autenticação"])


@roteador.post("/login", response_model=TokenAcesso)
async def login(
    formulario: Annotated[OAuth2PasswordRequestForm, Depends()],
    configuracao: Annotated[Configuracao, Depends(obter_configuracao_atual)],
) -> TokenAcesso:
    servico = ServicoAutenticacao(configuracao)
    return await servico.autenticar(formulario.username, formulario.password)


@roteador.get("/eu", response_model=AdministradorLer)
async def eu(
    credencial: Annotated[CredencialAutenticada, Depends(exigir_admin)],
    configuracao: Annotated[Configuracao, Depends(obter_configuracao_atual)],
) -> AdministradorLer:
    servico = ServicoAutenticacao(configuracao)
    return await servico.obter_administrador()
