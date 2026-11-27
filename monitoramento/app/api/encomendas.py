from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.cliente_transportadora import ClienteTransportadora
from app.core.banco_dados import obter_sessao
from app.core.configuracao import Configuracao
from app.core.dependencias import (
    exigir_usuario,
    obter_cliente_transportadora,
    obter_configuracao_atual,
)
from app.core.erros import ErroDeDominio
from app.core.seguranca import UsuarioAutenticado
from app.models.enums import StatusEncomenda
from app.schemas.encomenda import (
    EncomendaAtualizar,
    EncomendaCriar,
    EncomendaLer,
)
from app.services.maquina_de_estados import grupo_do_status
from app.services.servico_encomenda import ServicoEncomenda

roteador = APIRouter(prefix="/encomendas", tags=["encomendas"])


@roteador.post("", response_model=EncomendaLer, status_code=201)
async def criar_encomenda(
    dados: EncomendaCriar,
    usuario: Annotated[UsuarioAutenticado, Depends(exigir_usuario)],
    sessao: Annotated[AsyncSession, Depends(obter_sessao)],
    configuracao: Annotated[Configuracao, Depends(obter_configuracao_atual)],
    cliente_transportadora: Annotated[ClienteTransportadora, Depends(obter_cliente_transportadora)],
) -> EncomendaLer:
    servico = ServicoEncomenda(sessao)
    agora = datetime.now(UTC)
    encomenda = await servico.criar(
        usuario_id=usuario.id,
        codigo_rastreio=dados.codigo_rastreio,
        descricao=dados.descricao,
        vendedor=dados.vendedor,
        agora=agora,
    )
    encomenda = await servico.registrar_na_transportadora(
        encomenda,
        cliente_transportadora,
        datetime.now(UTC),
        configuracao,
    )
    return _para_ler(encomenda)


@roteador.get("", response_model=list[EncomendaLer])
async def listar_encomendas(
    usuario: Annotated[UsuarioAutenticado, Depends(exigir_usuario)],
    sessao: Annotated[AsyncSession, Depends(obter_sessao)],
    grupo: Annotated[str | None, Query()] = None,
) -> list[EncomendaLer]:
    if grupo is not None and grupo not in {
        "nao_encaminhadas",
        "a_caminho",
        "entregues",
    }:
        raise ErroDeDominio("Grupo inválido", "GRUPO_INVALIDO", 422)
    servico = ServicoEncomenda(sessao)
    encomendas = await servico.listar_por_usuario(usuario.id, grupo)
    return [_para_ler(e) for e in encomendas]


@roteador.get("/{encomenda_id}", response_model=EncomendaLer)
async def obter_encomenda(
    encomenda_id: Annotated[int, Path()],
    usuario: Annotated[UsuarioAutenticado, Depends(exigir_usuario)],
    sessao: Annotated[AsyncSession, Depends(obter_sessao)],
) -> EncomendaLer:
    servico = ServicoEncomenda(sessao)
    encomenda = await servico.obter_por_id_para_usuario(usuario.id, encomenda_id)
    return _para_ler(encomenda)


@roteador.patch("/{encomenda_id}", response_model=EncomendaLer)
async def atualizar_encomenda(
    encomenda_id: Annotated[int, Path()],
    dados: EncomendaAtualizar,
    usuario: Annotated[UsuarioAutenticado, Depends(exigir_usuario)],
    sessao: Annotated[AsyncSession, Depends(obter_sessao)],
) -> EncomendaLer:
    servico = ServicoEncomenda(sessao)
    agora = datetime.now(UTC)
    encomenda = await servico.atualizar(
        usuario_id=usuario.id,
        encomenda_id=encomenda_id,
        descricao=dados.descricao,
        vendedor=dados.vendedor,
        agora=agora,
    )
    return _para_ler(encomenda)


@roteador.delete("/{encomenda_id}", status_code=204)
async def excluir_encomenda(
    encomenda_id: Annotated[int, Path()],
    usuario: Annotated[UsuarioAutenticado, Depends(exigir_usuario)],
    sessao: Annotated[AsyncSession, Depends(obter_sessao)],
) -> None:
    servico = ServicoEncomenda(sessao)
    await servico.excluir(usuario.id, encomenda_id)


@roteador.post("/{encomenda_id}/registrar", response_model=EncomendaLer, status_code=202)
async def registrar_novamente(
    encomenda_id: Annotated[int, Path()],
    usuario: Annotated[UsuarioAutenticado, Depends(exigir_usuario)],
    sessao: Annotated[AsyncSession, Depends(obter_sessao)],
) -> EncomendaLer:
    servico = ServicoEncomenda(sessao)
    encomenda = await servico.reiniciar_registro(
        usuario.id,
        encomenda_id,
        datetime.now(UTC),
    )
    return _para_ler(encomenda)


def _para_ler(encomenda) -> EncomendaLer:
    historico = [
        {
            "status_anterior": item.status_anterior,
            "status_novo": item.status_novo,
            "ocorrido_em": item.ocorrido_em,
            "id_evento": item.id_evento,
        }
        for item in (encomenda.historico or [])
    ]
    return EncomendaLer(
        id=encomenda.id,
        codigo_rastreio=encomenda.codigo_rastreio,
        descricao=encomenda.descricao,
        vendedor=encomenda.vendedor,
        status=encomenda.status,
        grupo=grupo_do_status(StatusEncomenda(encomenda.status)),
        entregue_em=encomenda.entregue_em,
        criado_em=encomenda.criado_em,
        atualizado_em=encomenda.atualizado_em,
        historico=historico,
    )
