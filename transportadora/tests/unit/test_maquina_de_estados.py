import pytest

from app.models.enums import StatusRemessa
from app.services import maquina_de_estados


@pytest.mark.parametrize(
    ("status_atual", "proximo"),
    [
        (StatusRemessa.AGUARDANDO_ENVIO, StatusRemessa.POSTADO),
        (StatusRemessa.POSTADO, StatusRemessa.EM_TRANSITO),
        (StatusRemessa.EM_TRANSITO, StatusRemessa.SAIU_PARA_ENTREGA),
        (StatusRemessa.SAIU_PARA_ENTREGA, StatusRemessa.ENTREGUE),
    ],
)
def test_proximo_status_retorna_a_proxima_acao_valida(
    status_atual: StatusRemessa,
    proximo: StatusRemessa,
) -> None:
    assert maquina_de_estados.proximo_status(status_atual) == proximo


def test_proximo_status_de_entregue_e_nulo() -> None:
    assert maquina_de_estados.proximo_status(StatusRemessa.ENTREGUE) is None


def test_proximo_status_de_cada_status_do_enum() -> None:
    esperado = {
        StatusRemessa.AGUARDANDO_ENVIO: StatusRemessa.POSTADO,
        StatusRemessa.POSTADO: StatusRemessa.EM_TRANSITO,
        StatusRemessa.EM_TRANSITO: StatusRemessa.SAIU_PARA_ENTREGA,
        StatusRemessa.SAIU_PARA_ENTREGA: StatusRemessa.ENTREGUE,
        StatusRemessa.ENTREGUE: None,
    }

    assert {
        status: maquina_de_estados.proximo_status(status) for status in StatusRemessa
    } == esperado
