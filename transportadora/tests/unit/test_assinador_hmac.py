from app.core.assinador_hmac import assinar

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
ASSINATURA_ESPERADA = "sha256=875c9c64ac5b3fb7dfcb89ab9de1f73861166b2bc91b22acceebdb6b4b91bee9"
CABECALHOS_ESPERADOS = {
    "X-Carimbo-Tempo": "1763487730",
    "X-Assinatura": ASSINATURA_ESPERADA,
}


def test_assinar_vetor_de_teste_compartilhado() -> None:
    assert assinar(SEGREDO, CARIMBO_TEMPO, CORPO_BRUTO) == CABECALHOS_ESPERADOS


def test_assinar_e_deterministico_para_os_mesmos_dados() -> None:
    primeiro = assinar(SEGREDO, CARIMBO_TEMPO, CORPO_BRUTO)
    segundo = assinar(SEGREDO, CARIMBO_TEMPO, CORPO_BRUTO)

    assert primeiro == segundo == CABECALHOS_ESPERADOS


def test_assinar_gera_assinatura_com_prefixo_sha256_e_resumo_hexadecimal() -> None:
    assinatura = assinar(SEGREDO, CARIMBO_TEMPO, CORPO_BRUTO)["X-Assinatura"]

    assert assinatura.startswith("sha256=")
    resumo = assinatura.removeprefix("sha256=")
    assert len(resumo) == 64
    assert int(resumo, 16) >= 0


def test_assinar_muda_a_assinatura_quando_o_carimbo_muda() -> None:
    cabecalhos = assinar(SEGREDO, CARIMBO_TEMPO + 1, CORPO_BRUTO)

    assert cabecalhos["X-Carimbo-Tempo"] == str(CARIMBO_TEMPO + 1)
    assert cabecalhos["X-Assinatura"] != ASSINATURA_ESPERADA


def test_assinar_muda_a_assinatura_quando_o_corpo_muda_em_um_byte() -> None:
    corpo_alterado = CORPO_BRUTO[:-1] + b"!"

    cabecalhos = assinar(SEGREDO, CARIMBO_TEMPO, corpo_alterado)

    assert cabecalhos["X-Assinatura"] != ASSINATURA_ESPERADA


def test_assinar_muda_a_assinatura_quando_o_segredo_muda() -> None:
    cabecalhos = assinar(f"{SEGREDO}-outro", CARIMBO_TEMPO, CORPO_BRUTO)

    assert cabecalhos["X-Assinatura"] != ASSINATURA_ESPERADA
