from app.models.enums import StatusEncomenda

ORDEM_STATUS: dict[StatusEncomenda, int] = {
    StatusEncomenda.REGISTRO_PENDENTE: 0,
    StatusEncomenda.FALHA_NO_REGISTRO: 0,
    StatusEncomenda.AGUARDANDO_ENVIO: 1,
    StatusEncomenda.POSTADO: 2,
    StatusEncomenda.EM_TRANSITO: 3,
    StatusEncomenda.SAIU_PARA_ENTREGA: 4,
    StatusEncomenda.ENTREGUE: 5,
}

GRUPO_POR_STATUS: dict[StatusEncomenda, str] = {
    StatusEncomenda.REGISTRO_PENDENTE: "nao_encaminhadas",
    StatusEncomenda.FALHA_NO_REGISTRO: "nao_encaminhadas",
    StatusEncomenda.AGUARDANDO_ENVIO: "nao_encaminhadas",
    StatusEncomenda.POSTADO: "nao_encaminhadas",
    StatusEncomenda.EM_TRANSITO: "a_caminho",
    StatusEncomenda.SAIU_PARA_ENTREGA: "a_caminho",
    StatusEncomenda.ENTREGUE: "entregues",
}


def grupo_do_status(status: StatusEncomenda) -> str:
    return GRUPO_POR_STATUS[status]


def pode_aplicar_evento(status_atual: StatusEncomenda, status_evento: StatusEncomenda) -> bool:
    return ORDEM_STATUS[status_evento] > ORDEM_STATUS[status_atual]
