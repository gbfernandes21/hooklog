import asyncio

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.configuracao import Configuracao
from app.core.erros import ErroDeDominio
from app.core.seguranca import (
    UsuarioAutenticado,
    autenticar_admin,
    criar_token_acesso,
    gerar_hash_senha,
    verificar_senha,
)
from app.models.enums import Papel
from app.models.usuario import Usuario
from app.repositories.repositorio_usuario import RepositorioUsuario
from app.schemas.usuario import (
    TokenAcesso,
    UsuarioAutenticadoLer,
    UsuarioLer,
    UsuarioRegistro,
)


class ServicoAutenticacao:
    def __init__(self, sessao: AsyncSession, configuracao: Configuracao) -> None:
        self._sessao = sessao
        self._configuracao = configuracao
        self._repositorio = RepositorioUsuario(sessao)

    async def registrar(self, dados: UsuarioRegistro) -> UsuarioLer:
        if dados.email == self._configuracao.admin_email:
            raise ErroDeDominio("E-mail já cadastrado", "EMAIL_JA_CADASTRADO", 409)

        existente = await self._repositorio.obter_por_email(dados.email)
        if existente is not None:
            raise ErroDeDominio("E-mail já cadastrado", "EMAIL_JA_CADASTRADO", 409)

        senha_hash = await asyncio.to_thread(gerar_hash_senha, dados.senha)
        try:
            usuario = await self._repositorio.criar(
                Usuario(email=dados.email, senha_hash=senha_hash)
            )
            await self._sessao.commit()
        except IntegrityError as erro:
            await self._sessao.rollback()
            raise ErroDeDominio("E-mail já cadastrado", "EMAIL_JA_CADASTRADO", 409) from erro

        await self._sessao.refresh(usuario)
        return UsuarioLer(
            id=usuario.id,
            email=usuario.email,
            papel=Papel.USER,
            criado_em=usuario.criado_em,
        )

    async def autenticar(self, email: str, senha: str) -> TokenAcesso:
        email_normalizado = email.strip().lower()

        if email_normalizado == self._configuracao.admin_email:
            if autenticar_admin(email_normalizado, senha, self._configuracao):
                return TokenAcesso(access_token=criar_token_acesso("admin", Papel.ADMIN))
            raise ErroDeDominio("Credenciais inválidas", "CREDENCIAIS_INVALIDAS", 401)

        usuario = await self._repositorio.obter_por_email(email_normalizado)
        if usuario is None:
            raise ErroDeDominio("Credenciais inválidas", "CREDENCIAIS_INVALIDAS", 401)

        senha_confere = await asyncio.to_thread(verificar_senha, senha, usuario.senha_hash)
        if not senha_confere:
            raise ErroDeDominio("Credenciais inválidas", "CREDENCIAIS_INVALIDAS", 401)

        return TokenAcesso(access_token=criar_token_acesso(usuario.id, Papel.USER))

    async def obter_usuario_autenticado(self, usuario: UsuarioAutenticado) -> UsuarioAutenticadoLer:
        if usuario.papel is Papel.ADMIN:
            return UsuarioAutenticadoLer(
                id=None,
                email=self._configuracao.admin_email,
                papel=Papel.ADMIN,
            )

        registro = await self._repositorio.obter_por_id(usuario.id)
        if registro is None:
            raise ErroDeDominio("Token inválido", "TOKEN_INVALIDO", 401)

        return UsuarioAutenticadoLer(
            id=registro.id,
            email=registro.email,
            papel=Papel.USER,
        )
