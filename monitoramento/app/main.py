import logging
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.api.autenticacao import roteador as roteador_autenticacao
from app.core.banco_dados import obter_motor
from app.core.erros import ErroDeDominio, manipulador_erro_dominio

logger = logging.getLogger(__name__)

app = FastAPI(title="HookLog Monitoramento")
app.include_router(roteador_autenticacao)
app.add_exception_handler(ErroDeDominio, manipulador_erro_dominio)


@app.get("/health")
async def verificar_saude(
    motor: Annotated[AsyncEngine, Depends(obter_motor)],
) -> JSONResponse:
    try:
        async with motor.connect() as conexao:
            await conexao.execute(text("SELECT 1"))
    except (OSError, SQLAlchemyError):
        logger.warning("Banco de dados indisponível na verificação de saúde")
        return JSONResponse(
            status_code=503,
            content={"status": "erro", "servico": "monitoramento"},
        )

    return JSONResponse(
        status_code=200,
        content={"status": "ok", "servico": "monitoramento"},
    )
