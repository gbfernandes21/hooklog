from fastapi import Request
from fastapi.responses import JSONResponse


class ErroDeDominio(Exception):
    def __init__(self, mensagem: str, codigo: str, status_code: int) -> None:
        self.mensagem = mensagem
        self.codigo = codigo
        self.status_code = status_code
        super().__init__(mensagem)


async def manipulador_erro_dominio(request: Request, exc: ErroDeDominio) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detalhe": exc.mensagem, "codigo": exc.codigo},
    )
