import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.api.autenticacao import roteador as roteador_autenticacao
from app.api.logs_webhook import roteador as roteador_logs_webhook
from app.api.remessas import roteador as roteador_remessas
from app.core.banco_dados import FabricaSessao, obter_motor
from app.core.configuracao import obter_configuracao
from app.core.erros import ErroDeDominio, manipulador_erro_dominio
from app.workers.despachante_webhook import laco_despachante_webhook

logger = logging.getLogger(__name__)

CAMINHO_STATIC = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    configuracao = obter_configuracao()
    cliente_http = httpx.AsyncClient(timeout=configuracao.timeout_envio_webhook_segundos)
    app.state.cliente_http = cliente_http

    tarefa_despachante = asyncio.create_task(
        laco_despachante_webhook(
            FabricaSessao,
            cliente_http,
            configuracao.intervalo_rotina_webhook_segundos,
            configuracao.concorrencia_maxima_webhook,
            configuracao,
        )
    )

    try:
        yield
    finally:
        tarefa_despachante.cancel()
        with suppress(asyncio.CancelledError):
            await tarefa_despachante
        await cliente_http.aclose()


app = FastAPI(title="HookLog Transportadora", lifespan=lifespan)
app.include_router(roteador_autenticacao)
app.include_router(roteador_remessas)
app.include_router(roteador_logs_webhook)
app.add_exception_handler(ErroDeDominio, manipulador_erro_dominio)
app.mount("/static", StaticFiles(directory=CAMINHO_STATIC), name="static")


@app.get("/", response_class=FileResponse)
async def pagina_transportadora():
    return CAMINHO_STATIC / "index.html"


@app.get("/favicon.svg", response_class=FileResponse)
async def favicon():
    return CAMINHO_STATIC / "favicon.svg"


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
            content={"status": "erro", "servico": "transportadora"},
        )

    return JSONResponse(
        status_code=200,
        content={"status": "ok", "servico": "transportadora"},
    )
