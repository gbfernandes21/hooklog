from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.banco_dados import obter_sessao
from app.core.configuracao import Configuracao
from app.core.dependencias import obter_configuracao_atual, obter_usuario_atual
from app.core.seguranca import UsuarioAutenticado
from app.schemas.usuario import (
    TokenAcesso,
    UsuarioAutenticadoLer,
    UsuarioLer,
    UsuarioRegistro,
)
from app.services.servico_autenticacao import ServicoAutenticacao

roteador = APIRouter(prefix="/autenticacao", tags=["autenticação"])


@roteador.post("/registro", response_model=UsuarioLer, status_code=201)
async def registrar(
    dados: UsuarioRegistro,
    sessao: Annotated[AsyncSession, Depends(obter_sessao)],
    configuracao: Annotated[Configuracao, Depends(obter_configuracao_atual)],
) -> UsuarioLer:
    servico = ServicoAutenticacao(sessao, configuracao)
    return await servico.registrar(dados)


@roteador.post("/login", response_model=TokenAcesso)
async def login(
    formulario: Annotated[OAuth2PasswordRequestForm, Depends()],
    sessao: Annotated[AsyncSession, Depends(obter_sessao)],
    configuracao: Annotated[Configuracao, Depends(obter_configuracao_atual)],
) -> TokenAcesso:
    servico = ServicoAutenticacao(sessao, configuracao)
    return await servico.autenticar(formulario.username, formulario.password)


@roteador.get("/eu", response_model=UsuarioAutenticadoLer)
async def eu(
    usuario: Annotated[UsuarioAutenticado, Depends(obter_usuario_atual)],
    sessao: Annotated[AsyncSession, Depends(obter_sessao)],
    configuracao: Annotated[Configuracao, Depends(obter_configuracao_atual)],
) -> UsuarioAutenticadoLer:
    servico = ServicoAutenticacao(sessao, configuracao)
    return await servico.obter_usuario_autenticado(usuario)
