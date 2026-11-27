import asyncio
import hashlib
import hmac
import json
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import httpx
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.dependencias import obter_relogio
from app.main import app
from app.models.encomenda import Encomenda
from app.models.enums import StatusEncomenda
from app.models.evento_processado import EventoProcessado
from app.models.historico_status import HistoricoStatus
from app.models.usuario import Usuario

ADMIN_EMAIL = "admin@hooklog.test"
ADMIN_SENHA = "senha-admin-123"
SEGREDO_WEBHOOK = "segredo-webhook-teste"
AGORA = datetime(2026, 11, 30, 12, 0, 0, tzinfo=UTC)


@pytest_asyncio.fixture(autouse=True)
async def relogio_fixo() -> AsyncGenerator[None, None]:
    anterior = app.dependency_overrides.get(obter_relogio)

    async def _relogio() -> datetime:
        return AGORA

    app.dependency_overrides[obter_relogio] = _relogio
    try:
        yield
    finally:
        if anterior is not None:
            app.dependency_overrides[obter_relogio] = anterior
        else:
            app.dependency_overrides.pop(obter_relogio, None)


def _assinar(corpo_bruto: bytes, carimbo_tempo: int | None = None) -> tuple[str, str]:
    if carimbo_tempo is None:
        carimbo_tempo = int(AGORA.timestamp())
    conteudo = f"{carimbo_tempo}.".encode() + corpo_bruto
    resumo = hmac.new(SEGREDO_WEBHOOK.encode(), conteudo, hashlib.sha256).hexdigest()
    return str(carimbo_tempo), f"sha256={resumo}"


def _corpo_evento(
    id_evento: str,
    codigo_rastreio: str,
    status: str,
    tipo_evento: str = "remessa.status_alterado",
    entregue_em: str | None = None,
    recebido_por: str | None = None,
) -> str:
    corpo = {
        "id_evento": id_evento,
        "tipo_evento": tipo_evento,
        "codigo_rastreio": codigo_rastreio,
        "status": status,
        "vendedor": "Transportadora LTDA",
        "ocorrido_em": AGORA.isoformat().replace("+00:00", "Z"),
    }
    if entregue_em is not None:
        corpo["entregue_em"] = entregue_em
    if recebido_por is not None:
        corpo["recebido_por"] = recebido_por
    return json.dumps(corpo, separators=(",", ":"))


async def _registrar_e_fazer_login(
    cliente: httpx.AsyncClient,
    email: str = "ana@exemplo.com",
    senha: str = "minhasenha123",
) -> str:
    await cliente.post(
        "/autenticacao/registro",
        json={"email": email, "senha": senha},
    )
    resposta = await cliente.post(
        "/autenticacao/login",
        data={"username": email, "password": senha},
    )
    assert resposta.status_code == 200
    return resposta.json()["access_token"]


async def _criar_encomenda_banco(
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
    usuario_id: int,
    codigo_rastreio: str,
    status: str = StatusEncomenda.AGUARDANDO_ENVIO.value,
    entregue_em: datetime | None = None,
) -> int:
    async with fabrica_sessao_teste() as sessao:
        encomenda = Encomenda(
            usuario_id=usuario_id,
            codigo_rastreio=codigo_rastreio,
            descricao="Fone de ouvido",
            vendedor="Vendedor Local LTDA",
            status=status,
            tentativas_registro=0,
            proxima_tentativa_em=None,
            entregue_em=entregue_em,
            criado_em=AGORA,
            atualizado_em=AGORA,
        )
        sessao.add(encomenda)
        await sessao.flush()
        sessao.add(
            HistoricoStatus(
                encomenda_id=encomenda.id,
                status_anterior=None,
                status_novo=status,
                ocorrido_em=AGORA,
                registrado_em=AGORA,
            )
        )
        await sessao.commit()
        return encomenda.id


async def _enviar_webhook(
    cliente: httpx.AsyncClient,
    corpo: str,
    carimbo_tempo: int | None = None,
    assinatura: str | None = None,
    com_cabecalhos: bool = True,
) -> httpx.Response:
    if com_cabecalhos:
        ct, ass = _assinar(corpo.encode(), carimbo_tempo)
        return await cliente.post(
            "/webhooks/transportadora",
            content=corpo.encode(),
            headers={
                "Content-Type": "application/json",
                "X-Carimbo-Tempo": ct,
                "X-Assinatura": ass,
            },
        )
    return await cliente.post(
        "/webhooks/transportadora",
        content=corpo.encode(),
        headers={"Content-Type": "application/json"},
    )


async def _obter_status_encomenda(
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
    codigo_rastreio: str,
) -> str | None:
    async with fabrica_sessao_teste() as sessao:
        resultado = await sessao.execute(
            select(Encomenda.status).where(Encomenda.codigo_rastreio == codigo_rastreio)
        )
        return resultado.scalar_one_or_none()


async def _contar_eventos_processados(
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
    id_evento: str,
) -> int:
    async with fabrica_sessao_teste() as sessao:
        resultado = await sessao.execute(
            select(func.count())
            .select_from(EventoProcessado)
            .where(EventoProcessado.id_evento == id_evento)
        )
        return resultado.scalar_one()


async def _contar_historico_por_evento(
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
    encomenda_id: int,
    id_evento: str,
) -> int:
    async with fabrica_sessao_teste() as sessao:
        resultado = await sessao.execute(
            select(func.count())
            .select_from(HistoricoStatus)
            .where(
                HistoricoStatus.encomenda_id == encomenda_id,
                HistoricoStatus.id_evento == id_evento,
            )
        )
        return resultado.scalar_one()


async def _obter_encomenda_id(
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
    codigo_rastreio: str,
) -> int | None:
    async with fabrica_sessao_teste() as sessao:
        resultado = await sessao.execute(
            select(Encomenda.id).where(Encomenda.codigo_rastreio == codigo_rastreio)
        )
        return resultado.scalar_one_or_none()


async def _registrar_usuario_banco(
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
    email: str,
) -> int:
    async with fabrica_sessao_teste() as sessao:
        from argon2 import PasswordHasher

        usuario = Usuario(
            email=email,
            senha_hash=PasswordHasher().hash("minhasenha123"),
            criado_em=AGORA,
        )
        sessao.add(usuario)
        await sessao.flush()
        await sessao.refresh(usuario)
        await sessao.commit()
        return usuario.id


# --- Evento valido ---


async def test_evento_valido_retorna_200_aplicado_e_atualiza_encomenda(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    usuario_id = await _registrar_usuario_banco(fabrica_sessao_teste, "ana@exemplo.com")
    encomenda_id = await _criar_encomenda_banco(
        fabrica_sessao_teste, usuario_id, "BR123456789", StatusEncomenda.AGUARDANDO_ENVIO.value
    )

    corpo = _corpo_evento(
        id_evento="evt-00000001",
        codigo_rastreio="BR123456789",
        status=StatusEncomenda.POSTADO.value,
    )
    resposta = await _enviar_webhook(cliente, corpo)

    assert resposta.status_code == 200
    assert resposta.json() == {"resultado": "aplicado"}

    assert (
        await _obter_status_encomenda(fabrica_sessao_teste, "BR123456789")
        == StatusEncomenda.POSTADO.value
    )
    assert await _contar_eventos_processados(fabrica_sessao_teste, "evt-00000001") == 1
    assert (
        await _contar_historico_por_evento(fabrica_sessao_teste, encomenda_id, "evt-00000001") == 1
    )


async def test_evento_entrega_preenche_entregue_em(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    usuario_id = await _registrar_usuario_banco(fabrica_sessao_teste, "ana@exemplo.com")
    await _criar_encomenda_banco(
        fabrica_sessao_teste,
        usuario_id,
        "BR123456789",
        StatusEncomenda.SAIU_PARA_ENTREGA.value,
    )

    entregue_em = "2026-11-30T17:42:10Z"
    corpo = _corpo_evento(
        id_evento="evt-entrega-001",
        codigo_rastreio="BR123456789",
        status=StatusEncomenda.ENTREGUE.value,
        tipo_evento="remessa.entregue",
        entregue_em=entregue_em,
        recebido_por="Maria Souza",
    )
    resposta = await _enviar_webhook(cliente, corpo)

    assert resposta.status_code == 200
    assert resposta.json() == {"resultado": "aplicado"}

    async with fabrica_sessao_teste() as sessao:
        resultado = await sessao.execute(
            select(Encomenda.entregue_em).where(Encomenda.codigo_rastreio == "BR123456789")
        )
        entregue = resultado.scalar_one()
    assert entregue is not None
    assert entregue.isoformat().replace("+00:00", "Z") == entregue_em


# --- Seguranca (HMAC) ---


async def test_assinatura_errada_retorna_401_e_nada_altera(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    usuario_id = await _registrar_usuario_banco(fabrica_sessao_teste, "ana@exemplo.com")
    await _criar_encomenda_banco(
        fabrica_sessao_teste, usuario_id, "BR123456789", StatusEncomenda.AGUARDANDO_ENVIO.value
    )

    corpo = _corpo_evento(
        id_evento="evt-senha-001",
        codigo_rastreio="BR123456789",
        status=StatusEncomenda.POSTADO.value,
    )
    ct, _ = _assinar(corpo.encode())
    resposta = await cliente.post(
        "/webhooks/transportadora",
        content=corpo.encode(),
        headers={
            "Content-Type": "application/json",
            "X-Carimbo-Tempo": ct,
            "X-Assinatura": "sha256=errado",
        },
    )

    assert resposta.status_code == 401
    assert resposta.json()["codigo"] == "ASSINATURA_INVALIDA"
    assert (
        await _obter_status_encomenda(fabrica_sessao_teste, "BR123456789")
        == StatusEncomenda.AGUARDANDO_ENVIO.value
    )


async def test_carimbo_antigo_fora_da_janela_retorna_401(
    cliente: httpx.AsyncClient,
) -> None:
    corpo = _corpo_evento(
        id_evento="evt-antigo-001",
        codigo_rastreio="BR999999999",
        status=StatusEncomenda.POSTADO.value,
    )
    carimbo_antigo = int((AGORA - timedelta(seconds=100000)).timestamp())
    ct, ass = _assinar(corpo.encode(), carimbo_antigo)
    resposta = await cliente.post(
        "/webhooks/transportadora",
        content=corpo.encode(),
        headers={
            "Content-Type": "application/json",
            "X-Carimbo-Tempo": ct,
            "X-Assinatura": ass,
        },
    )

    assert resposta.status_code == 401
    assert resposta.json()["codigo"] == "ASSINATURA_INVALIDA"


async def test_sem_cabecalhos_hmac_retorna_401(cliente: httpx.AsyncClient) -> None:
    corpo = _corpo_evento(
        id_evento="evt-semcab-001",
        codigo_rastreio="BR999999999",
        status=StatusEncomenda.POSTADO.value,
    )
    resposta = await cliente.post(
        "/webhooks/transportadora",
        content=corpo.encode(),
        headers={"Content-Type": "application/json"},
    )

    assert resposta.status_code == 401
    assert resposta.json()["codigo"] == "ASSINATURA_INVALIDA"


async def test_corpo_invalido_com_assinatura_valida_retorna_422(
    cliente: httpx.AsyncClient,
) -> None:
    corpo_invalido = json.dumps({"id_evento": "evt-invalido-001", "codigo_rastreio": "BR999999999"})
    ct, ass = _assinar(corpo_invalido.encode())
    resposta = await cliente.post(
        "/webhooks/transportadora",
        content=corpo_invalido.encode(),
        headers={
            "Content-Type": "application/json",
            "X-Carimbo-Tempo": ct,
            "X-Assinatura": ass,
        },
    )

    assert resposta.status_code == 422


# --- Idempotencia ---


async def test_evento_duplicado_retorna_200_duplicado_e_nada_altera(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    usuario_id = await _registrar_usuario_banco(fabrica_sessao_teste, "ana@exemplo.com")
    encomenda_id = await _criar_encomenda_banco(
        fabrica_sessao_teste, usuario_id, "BR123456789", StatusEncomenda.AGUARDANDO_ENVIO.value
    )

    corpo = _corpo_evento(
        id_evento="evt-dup-001",
        codigo_rastreio="BR123456789",
        status=StatusEncomenda.POSTADO.value,
    )
    primeira = await _enviar_webhook(cliente, corpo)
    segunda = await _enviar_webhook(cliente, corpo)

    assert primeira.status_code == 200
    assert primeira.json() == {"resultado": "aplicado"}
    assert segunda.status_code == 200
    assert segunda.json() == {"resultado": "duplicado"}

    assert (
        await _obter_status_encomenda(fabrica_sessao_teste, "BR123456789")
        == StatusEncomenda.POSTADO.value
    )
    assert await _contar_eventos_processados(fabrica_sessao_teste, "evt-dup-001") == 1
    assert (
        await _contar_historico_por_evento(fabrica_sessao_teste, encomenda_id, "evt-dup-001") == 1
    )


# --- Encomenda e transicao ---


async def test_codigo_rastreio_desconhecido_retorna_404(cliente: httpx.AsyncClient) -> None:
    corpo = _corpo_evento(
        id_evento="evt-404-001",
        codigo_rastreio="BRINEEXISTENTE",
        status=StatusEncomenda.POSTADO.value,
    )
    resposta = await _enviar_webhook(cliente, corpo)

    assert resposta.status_code == 404
    assert resposta.json()["codigo"] == "ENCOMENDA_NAO_ENCONTRADA"


async def test_status_igual_ao_atual_retorna_409(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    usuario_id = await _registrar_usuario_banco(fabrica_sessao_teste, "ana@exemplo.com")
    await _criar_encomenda_banco(
        fabrica_sessao_teste, usuario_id, "BR123456789", StatusEncomenda.POSTADO.value
    )

    corpo = _corpo_evento(
        id_evento="evt-409-001",
        codigo_rastreio="BR123456789",
        status=StatusEncomenda.POSTADO.value,
    )
    resposta = await _enviar_webhook(cliente, corpo)

    assert resposta.status_code == 409
    assert resposta.json()["codigo"] == "TRANSICAO_INVALIDA"


async def test_status_anterior_ao_atual_retorna_409(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    usuario_id = await _registrar_usuario_banco(fabrica_sessao_teste, "ana@exemplo.com")
    await _criar_encomenda_banco(
        fabrica_sessao_teste, usuario_id, "BR123456789", StatusEncomenda.EM_TRANSITO.value
    )

    corpo = _corpo_evento(
        id_evento="evt-409-002",
        codigo_rastreio="BR123456789",
        status=StatusEncomenda.POSTADO.value,
    )
    resposta = await _enviar_webhook(cliente, corpo)

    assert resposta.status_code == 409
    assert resposta.json()["codigo"] == "TRANSICAO_INVALIDA"


async def test_pulo_para_frente_e_registro_pendente_sao_aplicados(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    usuario_id = await _registrar_usuario_banco(fabrica_sessao_teste, "ana@exemplo.com")

    # Pulando intermediario: AGUARDANDO_ENVIO -> EM_TRANSITO
    await _criar_encomenda_banco(
        fabrica_sessao_teste, usuario_id, "BR000000001", StatusEncomenda.AGUARDANDO_ENVIO.value
    )
    resposta = await _enviar_webhook(
        cliente,
        _corpo_evento(
            id_evento="evt-pulo-001",
            codigo_rastreio="BR000000001",
            status=StatusEncomenda.EM_TRANSITO.value,
        ),
    )
    assert resposta.status_code == 200
    assert resposta.json() == {"resultado": "aplicado"}
    assert (
        await _obter_status_encomenda(fabrica_sessao_teste, "BR000000001")
        == StatusEncomenda.EM_TRANSITO.value
    )

    # Encomenda ainda em REGISTRO_PENDENTE recebe primeiro evento
    await _criar_encomenda_banco(
        fabrica_sessao_teste, usuario_id, "BR000000002", StatusEncomenda.REGISTRO_PENDENTE.value
    )
    resposta = await _enviar_webhook(
        cliente,
        _corpo_evento(
            id_evento="evt-pulo-002",
            codigo_rastreio="BR000000002",
            status=StatusEncomenda.POSTADO.value,
        ),
    )
    assert resposta.status_code == 200
    assert resposta.json() == {"resultado": "aplicado"}
    assert (
        await _obter_status_encomenda(fabrica_sessao_teste, "BR000000002")
        == StatusEncomenda.POSTADO.value
    )


# --- Vendedor local nao e sobrescrito ---


async def test_vendedor_webhook_nao_sobrescreve_local(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    usuario_id = await _registrar_usuario_banco(fabrica_sessao_teste, "ana@exemplo.com")
    await _criar_encomenda_banco(
        fabrica_sessao_teste, usuario_id, "BR123456789", StatusEncomenda.AGUARDANDO_ENVIO.value
    )

    corpo = _corpo_evento(
        id_evento="evt-vend-001",
        codigo_rastreio="BR123456789",
        status=StatusEncomenda.POSTADO.value,
    )
    await _enviar_webhook(cliente, corpo)

    async with fabrica_sessao_teste() as sessao:
        resultado = await sessao.execute(
            select(Encomenda.vendedor).where(Encomenda.codigo_rastreio == "BR123456789")
        )
        vendedor = resultado.scalar_one()
    assert vendedor == "Vendedor Local LTDA"


# --- Sem JWT ---


async def test_webhook_funciona_sem_token_jwt(cliente: httpx.AsyncClient) -> None:
    corpo = _corpo_evento(
        id_evento="evt-snjwt-001",
        codigo_rastreio="BRINEEXISTENTE",
        status=StatusEncomenda.POSTADO.value,
    )
    resposta = await _enviar_webhook(cliente, corpo)
    # Nao existe, entao 404 (nao 401 por falta de JWT)
    assert resposta.status_code == 404


# --- Concorrencia ---


async def test_dez_webhooks_mesmo_id_evento_um_aplicado_e_nove_duplicado(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    usuario_id = await _registrar_usuario_banco(fabrica_sessao_teste, "ana@exemplo.com")
    await _criar_encomenda_banco(
        fabrica_sessao_teste, usuario_id, "BRCONC-001", StatusEncomenda.AGUARDANDO_ENVIO.value
    )

    corpo = _corpo_evento(
        id_evento="evt-conc-001",
        codigo_rastreio="BRCONC-001",
        status=StatusEncomenda.POSTADO.value,
    )

    respostas = await asyncio.gather(*[_enviar_webhook(cliente, corpo) for _ in range(10)])

    status_codes = sorted([r.status_code for r in respostas])
    resultados = sorted([r.json()["resultado"] for r in respostas])
    assert status_codes == [200] * 10
    assert resultados == ["aplicado"] + ["duplicado"] * 9
    assert await _contar_eventos_processados(fabrica_sessao_teste, "evt-conc-001") == 1


async def test_dois_webhooks_diferentes_mesma_encomenda_terminam_saiu_para_entrega(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    usuario_id = await _registrar_usuario_banco(fabrica_sessao_teste, "ana@exemplo.com")
    await _criar_encomenda_banco(
        fabrica_sessao_teste, usuario_id, "BRCONC-002", StatusEncomenda.AGUARDANDO_ENVIO.value
    )

    corpo_em_transito = _corpo_evento(
        id_evento="evt-conc-002-a",
        codigo_rastreio="BRCONC-002",
        status=StatusEncomenda.EM_TRANSITO.value,
    )
    corpo_saida = _corpo_evento(
        id_evento="evt-conc-002-b",
        codigo_rastreio="BRCONC-002",
        status=StatusEncomenda.SAIU_PARA_ENTREGA.value,
    )

    respostas = await asyncio.gather(
        _enviar_webhook(cliente, corpo_em_transito),
        _enviar_webhook(cliente, corpo_saida),
    )

    status_codes = sorted([r.status_code for r in respostas])
    assert status_codes in ([200, 200], [200, 409])
    assert (
        await _obter_status_encomenda(fabrica_sessao_teste, "BRCONC-002")
        == StatusEncomenda.SAIU_PARA_ENTREGA.value
    )
    encomenda_id = await _obter_encomenda_id(fabrica_sessao_teste, "BRCONC-002")
    assert encomenda_id is not None
    # Pelo menos o evento que avançou o status grava o historico
    aplicados = await _contar_historico_por_evento(
        fabrica_sessao_teste, encomenda_id, "evt-conc-002-a"
    ) + await _contar_historico_por_evento(fabrica_sessao_teste, encomenda_id, "evt-conc-002-b")
    assert aplicados >= 1
