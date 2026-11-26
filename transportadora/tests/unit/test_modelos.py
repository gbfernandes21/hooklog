from app.models import Base


def test_metadata_tem_as_tres_tabelas_da_transportadora() -> None:
    nomes = set(Base.metadata.tables.keys())

    assert nomes == {"remessas", "eventos_webhook", "tentativas_webhook"}


def test_remessa_tem_colunas_obrigatorias() -> None:
    colunas = {coluna.name for coluna in Base.metadata.tables["remessas"].columns}

    assert {
        "id",
        "codigo_rastreio",
        "vendedor",
        "status",
        "url_callback",
        "entregue_em",
        "recebido_por",
        "criado_em",
        "atualizado_em",
    }.issubset(colunas)


def test_eventos_webhook_tem_colunas_obrigatorias() -> None:
    colunas = {coluna.name for coluna in Base.metadata.tables["eventos_webhook"].columns}

    assert {
        "id",
        "remessa_id",
        "id_evento",
        "tipo_evento",
        "corpo",
        "estado",
        "total_tentativas",
        "proxima_tentativa_em",
        "ultimo_status_http",
        "ultimo_erro",
        "criado_em",
        "enviado_em",
    }.issubset(colunas)


def test_tentativas_webhook_tem_colunas_obrigatorias() -> None:
    colunas = {coluna.name for coluna in Base.metadata.tables["tentativas_webhook"].columns}

    assert {
        "id",
        "evento_webhook_id",
        "numero",
        "status_http",
        "erro",
        "duracao_ms",
        "tentou_em",
    }.issubset(colunas)
