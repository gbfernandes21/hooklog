from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.banco_dados import obter_sessao
from app.core.dependencias import (
    exigir_admin,
)
from app.core.erros import ErroDeDominio
from app.core.seguranca import UsuarioAutenticado
from app.models.enums import StatusEncomenda
from app.schemas.encomenda import EncomendaAdminLer
from app.services.maquina_de_estados import grupo_do_status
from app.services.servico_encomenda import ServicoEncomenda

roteador = APIRouter(prefix="/admin/encomendas", tags=["admin - encomendas"])


@roteador.get("", response_model=list[EncomendaAdminLer])
async def listar_todas(
    usuario: Annotated[UsuarioAutenticado, Depends(exigir_admin)],
    sessao: Annotated[AsyncSession, Depends(obter_sessao)],
    grupo: Annotated[str | None, Query()] = None,
    usuario_id: Annotated[int | None, Query()] = None,
) -> list[EncomendaAdminLer]:
    if grupo is not None and grupo not in {
        "nao_encaminhadas",
        "a_caminho",
        "entregues",
    }:
        raise ErroDeDominio("Grupo inválido", "GRUPO_INVALIDO", 422)
    servico = ServicoEncomenda(sessao)
    encomendas = await servico.listar_todas(grupo, usuario_id)
    return [_para_ler_admin(e) for e in encomendas]


@roteador.get("/{encomenda_id}", response_model=EncomendaAdminLer)
async def obter_por_id(
    encomenda_id: Annotated[int, Path()],
    usuario: Annotated[UsuarioAutenticado, Depends(exigir_admin)],
    sessao: Annotated[AsyncSession, Depends(obter_sessao)],
) -> EncomendaAdminLer:
    servico = ServicoEncomenda(sessao)
    encomenda = await servico.obter_por_id_para_admin(encomenda_id)
    return _para_ler_admin(encomenda)


def _para_ler_admin(encomenda) -> EncomendaAdminLer:
    historico = [
        {
            "status_anterior": item.status_anterior,
            "status_novo": item.status_novo,
            "ocorrido_em": item.ocorrido_em,
            "id_evento": item.id_evento,
        }
        for item in (encomenda.historico or [])
    ]
    return EncomendaAdminLer(
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
        usuario_id=encomenda.usuario_id,
        usuario_email=encomenda.usuario.email,
    )
