import pytest

from app.models.enums import StatusEncomenda
from app.services.maquina_de_estados import (
    ORDEM_STATUS,
    grupo_do_status,
    pode_aplicar_evento,
)

TODOS_OS_STATUS = list(StatusEncomenda)


@pytest.mark.parametrize(
    ("status", "ordem"),
    [
        (StatusEncomenda.REGISTRO_PENDENTE, 0),
        (StatusEncomenda.FALHA_NO_REGISTRO, 0),
        (StatusEncomenda.AGUARDANDO_ENVIO, 1),
        (StatusEncomenda.POSTADO, 2),
        (StatusEncomenda.EM_TRANSITO, 3),
        (StatusEncomenda.SAIU_PARA_ENTREGA, 4),
        (StatusEncomenda.ENTREGUE, 5),
    ],
)
def test_ordem_de_cada_status(status: StatusEncomenda, ordem: int) -> None:
    assert ORDEM_STATUS[status] == ordem


def test_ordem_status_contem_exatamente_todos_os_status() -> None:
    assert set(ORDEM_STATUS) == set(StatusEncomenda)


@pytest.mark.parametrize(
    ("status", "grupo"),
    [
        (StatusEncomenda.REGISTRO_PENDENTE, "nao_encaminhadas"),
        (StatusEncomenda.FALHA_NO_REGISTRO, "nao_encaminhadas"),
        (StatusEncomenda.AGUARDANDO_ENVIO, "nao_encaminhadas"),
        (StatusEncomenda.POSTADO, "nao_encaminhadas"),
        (StatusEncomenda.EM_TRANSITO, "a_caminho"),
        (StatusEncomenda.SAIU_PARA_ENTREGA, "a_caminho"),
        (StatusEncomenda.ENTREGUE, "entregues"),
    ],
)
def test_grupo_de_cada_status(status: StatusEncomenda, grupo: str) -> None:
    assert grupo_do_status(status) == grupo


@pytest.mark.parametrize(
    ("status_atual", "status_evento"),
    [
        (StatusEncomenda.REGISTRO_PENDENTE, StatusEncomenda.AGUARDANDO_ENVIO),
        (StatusEncomenda.REGISTRO_PENDENTE, StatusEncomenda.EM_TRANSITO),
        (StatusEncomenda.AGUARDANDO_ENVIO, StatusEncomenda.POSTADO),
        (StatusEncomenda.AGUARDANDO_ENVIO, StatusEncomenda.EM_TRANSITO),
        (StatusEncomenda.POSTADO, StatusEncomenda.SAIU_PARA_ENTREGA),
        (StatusEncomenda.EM_TRANSITO, StatusEncomenda.ENTREGUE),
        (StatusEncomenda.SAIU_PARA_ENTREGA, StatusEncomenda.ENTREGUE),
        (StatusEncomenda.AGUARDANDO_ENVIO, StatusEncomenda.ENTREGUE),
    ],
)
def test_pode_aplicar_evento_permite_avanco(
    status_atual: StatusEncomenda, status_evento: StatusEncomenda
) -> None:
    assert pode_aplicar_evento(status_atual, status_evento) is True


@pytest.mark.parametrize("status", TODOS_OS_STATUS)
def test_pode_aplicar_evento_recusa_status_igual(status: StatusEncomenda) -> None:
    assert pode_aplicar_evento(status, status) is False


@pytest.mark.parametrize(
    ("status_atual", "status_evento"),
    [
        (StatusEncomenda.FALHA_NO_REGISTRO, StatusEncomenda.REGISTRO_PENDENTE),
        (StatusEncomenda.REGISTRO_PENDENTE, StatusEncomenda.FALHA_NO_REGISTRO),
        (StatusEncomenda.POSTADO, StatusEncomenda.AGUARDANDO_ENVIO),
        (StatusEncomenda.EM_TRANSITO, StatusEncomenda.AGUARDANDO_ENVIO),
        (StatusEncomenda.EM_TRANSITO, StatusEncomenda.POSTADO),
        (StatusEncomenda.SAIU_PARA_ENTREGA, StatusEncomenda.EM_TRANSITO),
        (StatusEncomenda.ENTREGUE, StatusEncomenda.AGUARDANDO_ENVIO),
        (StatusEncomenda.ENTREGUE, StatusEncomenda.SAIU_PARA_ENTREGA),
    ],
)
def test_pode_aplicar_evento_recusa_status_anterior(
    status_atual: StatusEncomenda, status_evento: StatusEncomenda
) -> None:
    assert pode_aplicar_evento(status_atual, status_evento) is False
