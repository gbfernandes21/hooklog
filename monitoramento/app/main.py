import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.api.admin import roteador as roteador_admin
from app.api.autenticacao import roteador as roteador_autenticacao
from app.api.encomendas import roteador as roteador_encomendas
from app.clients.cliente_transportadora import ClienteTransportadora
from app.core.banco_dados import FabricaSessao, obter_motor
from app.core.configuracao import obter_configuracao
from app.core.erros import ErroDeDominio, manipulador_erro_dominio
from app.workers.registro_pendente import laco_registro_pendente

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configuracao = obter_configuracao()
    cliente_http = httpx.AsyncClient(timeout=configuracao.timeout_transportadora_segundos)
    cliente_transportadora = ClienteTransportadora(cliente_http, configuracao)
    app.state.cliente_transportadora = cliente_transportadora

    tarefa_registro = asyncio.create_task(
        laco_registro_pendente(
            FabricaSessao,
            cliente_transportadora,
            configuracao.intervalo_rotina_registro_segundos,
            configuracao.concorrencia_maxima_registro,
            configuracao,
        )
    )

    try:
        yield
    finally:
        tarefa_registro.cancel()
        with suppress(asyncio.CancelledError):
            await tarefa_registro
        await cliente_http.aclose()


app = FastAPI(title="HookLog Monitoramento", lifespan=lifespan)
app.include_router(roteador_autenticacao)
app.include_router(roteador_encomendas)
app.include_router(roteador_admin)
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
