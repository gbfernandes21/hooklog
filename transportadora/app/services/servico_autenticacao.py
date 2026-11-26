from app.core.configuracao import Configuracao
from app.core.erros import ErroDeDominio
from app.core.seguranca import autenticar_admin, criar_token_acesso
from app.models.enums import Papel
from app.schemas.autenticacao import AdministradorLer, TokenAcesso


class ServicoAutenticacao:
    def __init__(self, configuracao: Configuracao) -> None:
        self._configuracao = configuracao

    async def autenticar(self, email: str, senha: str) -> TokenAcesso:
        if not autenticar_admin(email, senha, self._configuracao):
            raise ErroDeDominio("Credenciais inválidas", "CREDENCIAIS_INVALIDAS", 401)

        return TokenAcesso(access_token=criar_token_acesso("admin", Papel.ADMIN))

    async def obter_administrador(self) -> AdministradorLer:
        return AdministradorLer(
            email=self._configuracao.admin_email,
            papel=Papel.ADMIN,
        )
