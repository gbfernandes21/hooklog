import json
from datetime import UTC, datetime, timedelta

import pytest

from app.services.verificador_hmac import verificar

SEGREDO = "segredo-de-teste-hmac"
CARIMBO_TEMPO = 1763487730
CORPO_BRUTO = (
    b'{"id_evento": "6f1c7d4e-2b0a-4f43-9c1a-1d7f3c2b9a10", '
    b'"tipo_evento": "remessa.entregue", '
    b'"codigo_rastreio": "BR123456789", '
    b'"status": "ENTREGUE", '
    b'"vendedor": "Loja Exemplo LTDA", '
    b'"ocorrido_em": "2026-11-18T17:42:10Z", '
    b'"entregue_em": "2026-11-18T17:42:10Z", '
    b'"recebido_por": "Maria Souza"}'
)
RESUMO_ESPERADO = "875c9c64ac5b3fb7dfcb89ab9de1f73861166b2bc91b22acceebdb6b4b91bee9"
ASSINATURA_ESPERADA = f"sha256={RESUMO_ESPERADO}"
AGORA = datetime.fromtimestamp(CARIMBO_TEMPO, tz=UTC)
TOLERANCIA_SEGUNDOS = 300


def _verificar(
    *,
    segredo: str = SEGREDO,
    carimbo_tempo: str = str(CARIMBO_TEMPO),
    assinatura: str = ASSINATURA_ESPERADA,
    corpo_bruto: bytes = CORPO_BRUTO,
    agora: datetime = AGORA,
) -> bool:
    return verificar(
        segredo=segredo,
        carimbo_tempo=carimbo_tempo,
        assinatura=assinatura,
        corpo_bruto=corpo_bruto,
        agora=agora,
        tolerancia_segundos=TOLERANCIA_SEGUNDOS,
    )


def test_verificar_aceita_vetor_de_teste_compartilhado() -> None:
    assert _verificar() is True


def test_verificar_rejeita_corpo_alterado_em_um_byte() -> None:
    corpo_alterado = CORPO_BRUTO[:-1] + b"!"

    assert _verificar(corpo_bruto=corpo_alterado) is False


def test_verificar_rejeita_carimbo_diferente() -> None:
    assert _verificar(carimbo_tempo=str(CARIMBO_TEMPO + 1)) is False


def test_verificar_rejeita_segredo_errado() -> None:
    assert _verificar(segredo=f"{SEGREDO}-errado") is False


def test_verificar_rejeita_assinatura_sem_prefixo_sha256() -> None:
    assert _verificar(assinatura=RESUMO_ESPERADO) is False


def test_verificar_rejeita_carimbo_nao_numerico() -> None:
    assert _verificar(carimbo_tempo="nao-e-numero") is False


@pytest.mark.parametrize("deslocamento", [-300, 300])
def test_verificar_aceita_carimbo_no_limite_da_janela(deslocamento: int) -> None:
    assert _verificar(agora=AGORA + timedelta(seconds=deslocamento)) is True


@pytest.mark.parametrize("deslocamento", [-301, 301])
def test_verificar_rejeita_carimbo_fora_da_janela(deslocamento: int) -> None:
    assert _verificar(agora=AGORA + timedelta(seconds=deslocamento)) is False


def test_verificar_usa_os_bytes_brutos_e_nao_json_reserializado() -> None:
    corpo_reserializado = json.dumps(json.loads(CORPO_BRUTO), separators=(",", ":")).encode()

    assert corpo_reserializado != CORPO_BRUTO
    assert _verificar(corpo_bruto=corpo_reserializado) is False
