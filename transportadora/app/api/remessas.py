from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.banco_dados import obter_sessao
from app.core.dependencias import (
    exigir_admin,
    exigir_admin_ou_chave_servico,
    exigir_chave_servico,
)
from app.core.seguranca import CredencialAutenticada
from app.models.enums import StatusRemessa
from app.models.remessa import Remessa
from app.schemas.remessa import (
    RemessaCriar,
    RemessaEntregar,
    RemessaLer,
    RemessaStatusAtualizar,
)
from app.services.maquina_de_estados import proximo_status
from app.services.servico_remessa import ServicoRemessa

roteador = APIRouter(prefix="/remessas", tags=["remessas"])


@roteador.post("", response_model=RemessaLer)
async def criar_remessa(
    dados: RemessaCriar,
    resposta: Response,
    _credencial: Annotated[None, Depends(exigir_chave_servico)],
    sessao: Annotated[AsyncSession, Depends(obter_sessao)],
) -> RemessaLer:
    servico = ServicoRemessa(sessao)
    resultado = await servico.criar(
        codigo_rastreio=dados.codigo_rastreio,
        vendedor=dados.vendedor,
        url_callback=dados.url_callback,
        agora=datetime.now(UTC),
    )
    resposta.status_code = 201 if resultado.criada else 200
    return _para_ler(resultado.remessa)


@roteador.get("", response_model=list[RemessaLer])
async def listar_remessas(
    _credencial: Annotated[CredencialAutenticada, Depends(exigir_admin)],
    sessao: Annotated[AsyncSession, Depends(obter_sessao)],
) -> list[RemessaLer]:
    servico = ServicoRemessa(sessao)
    return [_para_ler(remessa) for remessa in await servico.listar()]


@roteador.get("/{codigo_rastreio}", response_model=RemessaLer)
async def obter_remessa(
    codigo_rastreio: Annotated[str, Path()],
    _credencial: Annotated[None, Depends(exigir_admin_ou_chave_servico)],
    sessao: Annotated[AsyncSession, Depends(obter_sessao)],
) -> RemessaLer:
    servico = ServicoRemessa(sessao)
    remessa = await servico.obter_por_codigo(codigo_rastreio)
    return _para_ler(remessa)


@roteador.post("/{codigo_rastreio}/status", response_model=RemessaLer)
async def alterar_status(
    codigo_rastreio: Annotated[str, Path()],
    dados: RemessaStatusAtualizar,
    _credencial: Annotated[CredencialAutenticada, Depends(exigir_admin)],
    sessao: Annotated[AsyncSession, Depends(obter_sessao)],
) -> RemessaLer:
    servico = ServicoRemessa(sessao)
    remessa = await servico.mudar_status(
        codigo_rastreio=codigo_rastreio,
        novo_status=StatusRemessa(dados.status),
        agora=datetime.now(UTC),
    )
    return _para_ler(remessa)


@roteador.post("/{codigo_rastreio}/entregar", response_model=RemessaLer)
async def entregar_remessa(
    codigo_rastreio: Annotated[str, Path()],
    _credencial: Annotated[CredencialAutenticada, Depends(exigir_admin)],
    sessao: Annotated[AsyncSession, Depends(obter_sessao)],
    dados: RemessaEntregar | None = None,
) -> RemessaLer:
    servico = ServicoRemessa(sessao)
    remessa = await servico.entregar(
        codigo_rastreio=codigo_rastreio,
        recebido_por=dados.recebido_por if dados is not None else None,
        agora=datetime.now(UTC),
    )
    return _para_ler(remessa)


def _para_ler(remessa: Remessa) -> RemessaLer:
    status = StatusRemessa(remessa.status)
    return RemessaLer(
        id=remessa.id,
        codigo_rastreio=remessa.codigo_rastreio,
        vendedor=remessa.vendedor,
        status=status,
        proximo_status=proximo_status(status),
        url_callback=remessa.url_callback,
        entregue_em=remessa.entregue_em,
        recebido_por=remessa.recebido_por,
        criado_em=remessa.criado_em,
        atualizado_em=remessa.atualizado_em,
    )
