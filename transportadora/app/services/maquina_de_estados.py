from app.models.enums import StatusRemessa

_PROXIMO_STATUS: dict[StatusRemessa, StatusRemessa | None] = {
    StatusRemessa.AGUARDANDO_ENVIO: StatusRemessa.POSTADO,
    StatusRemessa.POSTADO: StatusRemessa.EM_TRANSITO,
    StatusRemessa.EM_TRANSITO: StatusRemessa.SAIU_PARA_ENTREGA,
    StatusRemessa.SAIU_PARA_ENTREGA: StatusRemessa.ENTREGUE,
    StatusRemessa.ENTREGUE: None,
}


def proximo_status(status_atual: StatusRemessa) -> StatusRemessa | None:
    return _PROXIMO_STATUS[status_atual]
