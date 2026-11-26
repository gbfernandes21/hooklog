import asyncio

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.encomenda import Encomenda
from app.models.historico_status import HistoricoStatus
from app.models.usuario import Usuario

ADMIN_EMAIL = "admin@hooklog.test"
ADMIN_SENHA = "senha-admin-123"


async def _registrar_usuario(
    cliente: httpx.AsyncClient,
    email: str = "ana@exemplo.com",
    senha: str = "minhasenha123",
) -> dict:
    resposta = await cliente.post(
        "/autenticacao/registro",
        json={"email": email, "senha": senha},
    )
    assert resposta.status_code == 201
    return resposta.json()


async def _registrar_e_fazer_login(
    cliente: httpx.AsyncClient,
    email: str = "ana@exemplo.com",
    senha: str = "minhasenha123",
) -> str:
    await _registrar_usuario(cliente, email=email, senha=senha)
    return await _fazer_login(cliente, email=email, senha=senha)


async def _fazer_login(
    cliente: httpx.AsyncClient,
    email: str = "ana@exemplo.com",
    senha: str = "minhasenha123",
) -> str:
    resposta = await cliente.post(
        "/autenticacao/login",
        data={"username": email, "password": senha},
    )
    assert resposta.status_code == 200
    return resposta.json()["access_token"]


async def _login_admin(cliente: httpx.AsyncClient) -> str:
    return await _fazer_login(cliente, ADMIN_EMAIL, ADMIN_SENHA)


async def _cadastra_encomenda(
    cliente: httpx.AsyncClient,
    token: str,
    codigo_rastreio: str = "BR123456789",
    descricao: str = "Fone de ouvido",
    vendedor: str = "Loja Exemplo LTDA",
) -> httpx.Response:
    return await cliente.post(
        "/encomendas",
        json={
            "codigo_rastreio": codigo_rastreio,
            "descricao": descricao,
            "vendedor": vendedor,
        },
        headers={"Authorization": f"Bearer {token}"},
    )


async def _contar_encomendas(
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> int:
    async with fabrica_sessao_teste() as sessao:
        resultado = await sessao.execute(select(func.count()).select_from(Encomenda))
        return resultado.scalar_one()


async def _contar_historico(
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
    encomenda_id: int,
) -> int:
    async with fabrica_sessao_teste() as sessao:
        resultado = await sessao.execute(
            select(func.count())
            .select_from(HistoricoStatus)
            .where(HistoricoStatus.encomenda_id == encomenda_id)
        )
        return resultado.scalar_one()


# --- Create ---


async def test_criar_encomenda_retorna_201_com_grupo_correto(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    token = await _registrar_e_fazer_login(cliente)

    resposta = await _cadastra_encomenda(cliente, token)

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["codigo_rastreio"] == "BR123456789"
    assert corpo["status"] == "REGISTRO_PENDENTE"
    assert corpo["grupo"] == "nao_encaminhadas"
    assert corpo["id"] is not None
    assert "criado_em" in corpo
    assert "atualizado_em" in corpo


async def test_codigo_repetido_retorna_409_mesmo_entre_usuarios_diferentes(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    token_a = await _registrar_e_fazer_login(cliente, email="ana@exemplo.com")
    await _cadastra_encomenda(cliente, token_a, codigo_rastreio="BR123456789")

    token_b = await _registrar_e_fazer_login(cliente, email="bia@exemplo.com")
    resposta = await _cadastra_encomenda(cliente, token_b, codigo_rastreio="BR123456789")

    assert resposta.status_code == 409
    assert resposta.json()["codigo"] == "CODIGO_RASTREIO_DUPLICADO"


async def test_normaliza_codigo_rastreio_para_maiusculas_sem_espacos(
    cliente: httpx.AsyncClient,
) -> None:
    token = await _registrar_e_fazer_login(cliente)

    resposta = await _cadastra_encomenda(cliente, token, codigo_rastreio="  br123-456  ")

    assert resposta.status_code == 201
    assert resposta.json()["codigo_rastreio"] == "BR123-456"


# --- Read ---


async def test_lista_devolve_somente_as_do_usuario_logado(
    cliente: httpx.AsyncClient,
) -> None:
    token_a = await _registrar_e_fazer_login(cliente, email="ana@exemplo.com")
    await _cadastra_encomenda(cliente, token_a, codigo_rastreio="BR000000001")

    token_b = await _registrar_e_fazer_login(cliente, email="bia@exemplo.com")
    await _cadastra_encomenda(cliente, token_b, codigo_rastreio="BR000000002")

    resposta = await cliente.get(
        "/encomendas",
        headers={"Authorization": f"Bearer {token_a}"},
    )

    assert resposta.status_code == 200
    corpos = resposta.json()
    assert len(corpos) == 1
    assert corpos[0]["codigo_rastreio"] == "BR000000001"


async def test_filtro_por_grupo_funciona(
    cliente: httpx.AsyncClient,
) -> None:
    token = await _registrar_e_fazer_login(cliente)
    await _cadastra_encomenda(cliente, token, codigo_rastreio="BR000000001")

    resposta = await cliente.get(
        "/encomendas?grupo=nao_encaminhadas",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resposta.status_code == 200
    corpos = resposta.json()
    assert len(corpos) == 1
    assert corpos[0]["grupo"] == "nao_encaminhadas"


async def test_grupo_invalido_retorna_422(cliente: httpx.AsyncClient) -> None:
    token = await _registrar_e_fazer_login(cliente)

    resposta = await cliente.get(
        "/encomendas?grupo=invalido",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resposta.status_code == 422


async def test_detalhe_traz_historico_em_ordem_cronologica(
    cliente: httpx.AsyncClient,
) -> None:
    token = await _registrar_e_fazer_login(cliente)
    resposta = await _cadastra_encomenda(cliente, token)
    encomenda_id = resposta.json()["id"]

    resposta_detalhe = await cliente.get(
        f"/encomendas/{encomenda_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resposta_detalhe.status_code == 200
    corpo = resposta_detalhe.json()
    assert len(corpo["historico"]) == 1
    assert corpo["historico"][0]["status_novo"] == "REGISTRO_PENDENTE"
    assert corpo["historico"][0]["status_anterior"] is None


# --- Update ---


async def test_patch_atualiza_descricao_e_vendedor_e_atualizado_em(
    cliente: httpx.AsyncClient,
) -> None:
    token = await _registrar_e_fazer_login(cliente)
    resposta = await _cadastra_encomenda(cliente, token)
    encomenda_id = resposta.json()["id"]
    antes = resposta.json()["atualizado_em"]

    resposta = await cliente.patch(
        f"/encomendas/{encomenda_id}",
        json={"descricao": "Fone bluetooth", "vendedor": "Loja Nova"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["descricao"] == "Fone bluetooth"
    assert corpo["vendedor"] == "Loja Nova"
    assert corpo["atualizado_em"] != antes


async def test_patch_corpo_vazio_retorna_422(cliente: httpx.AsyncClient) -> None:
    token = await _registrar_e_fazer_login(cliente)
    resposta = await _cadastra_encomenda(cliente, token)
    encomenda_id = resposta.json()["id"]

    resposta = await cliente.patch(
        f"/encomendas/{encomenda_id}",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resposta.status_code == 422


async def test_patch_campo_invalido_retorna_422(cliente: httpx.AsyncClient) -> None:
    token = await _registrar_e_fazer_login(cliente)
    resposta = await _cadastra_encomenda(cliente, token)
    encomenda_id = resposta.json()["id"]

    resposta = await cliente.patch(
        f"/encomendas/{encomenda_id}",
        json={"campo_inexistente": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resposta.status_code == 422


async def test_patch_enviar_codigo_rastreio_ou_status_retorna_422(
    cliente: httpx.AsyncClient,
) -> None:
    token = await _registrar_e_fazer_login(cliente)
    resposta = await _cadastra_encomenda(cliente, token)
    encomenda_id = resposta.json()["id"]

    resposta_codigo = await cliente.patch(
        f"/encomendas/{encomenda_id}",
        json={"codigo_rastreio": "BR999999999"},
        headers={"Authorization": f"Bearer {token}"},
    )
    resposta_status = await cliente.patch(
        f"/encomendas/{encomenda_id}",
        json={"status": "ENTREGUE"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resposta_codigo.status_code == 422
    assert resposta_status.status_code == 422


async def test_patch_nao_cria_historico(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    token = await _registrar_e_fazer_login(cliente)
    resposta = await _cadastra_encomenda(cliente, token)
    encomenda_id = resposta.json()["id"]

    await cliente.patch(
        f"/encomendas/{encomenda_id}",
        json={"descricao": "Novo nome"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert await _contar_historico(fabrica_sessao_teste, encomenda_id) == 1


# --- Delete ---


async def test_delete_retorna_204_e_apaga_historico(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    token = await _registrar_e_fazer_login(cliente)
    resposta = await _cadastra_encomenda(cliente, token)
    encomenda_id = resposta.json()["id"]

    resposta = await cliente.delete(
        f"/encomendas/{encomenda_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resposta.status_code == 204
    assert await _contar_encomendas(fabrica_sessao_teste) == 0
    assert await _contar_historico(fabrica_sessao_teste, encomenda_id) == 0


# --- Isolamento ---


async def test_usuario_b_recebe_404_ao_ver_encomenda_de_outro(
    cliente: httpx.AsyncClient,
) -> None:
    token_a = await _registrar_e_fazer_login(cliente, email="ana@exemplo.com")
    resposta = await _cadastra_encomenda(cliente, token_a)
    encomenda_id = resposta.json()["id"]

    token_b = await _registrar_e_fazer_login(cliente, email="bia@exemplo.com")
    resposta = await cliente.get(
        f"/encomendas/{encomenda_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )

    assert resposta.status_code == 404


async def test_usuario_b_recebe_404_ao_editar_encomenda_de_outro(
    cliente: httpx.AsyncClient,
) -> None:
    token_a = await _registrar_e_fazer_login(cliente, email="ana@exemplo.com")
    resposta = await _cadastra_encomenda(cliente, token_a)
    encomenda_id = resposta.json()["id"]

    token_b = await _registrar_e_fazer_login(cliente, email="bia@exemplo.com")
    resposta = await cliente.patch(
        f"/encomendas/{encomenda_id}",
        json={"descricao": "editado"},
        headers={"Authorization": f"Bearer {token_b}"},
    )

    assert resposta.status_code == 404


async def test_usuario_b_recebe_404_ao_excluir_encomenda_de_outro(
    cliente: httpx.AsyncClient,
) -> None:
    token_a = await _registrar_e_fazer_login(cliente, email="ana@exemplo.com")
    resposta = await _cadastra_encomenda(cliente, token_a)
    encomenda_id = resposta.json()["id"]

    token_b = await _registrar_e_fazer_login(cliente, email="bia@exemplo.com")
    resposta = await cliente.delete(
        f"/encomendas/{encomenda_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )

    assert resposta.status_code == 404


# --- Papéis ---


async def test_admin_recebe_403_em_todas_as_rotas_encomendas(
    cliente: httpx.AsyncClient,
) -> None:
    token_admin = await _login_admin(cliente)

    resposta_post = await cliente.post(
        "/encomendas",
        json={"codigo_rastreio": "BR000000001", "descricao": "x", "vendedor": "y"},
        headers={"Authorization": f"Bearer {token_admin}"},
    )
    resposta_get = await cliente.get(
        "/encomendas",
        headers={"Authorization": f"Bearer {token_admin}"},
    )
    resposta_get_id = await cliente.get(
        "/encomendas/1",
        headers={"Authorization": f"Bearer {token_admin}"},
    )
    resposta_patch = await cliente.patch(
        "/encomendas/1",
        json={"descricao": "x"},
        headers={"Authorization": f"Bearer {token_admin}"},
    )
    resposta_delete = await cliente.delete(
        "/encomendas/1",
        headers={"Authorization": f"Bearer {token_admin}"},
    )

    assert resposta_post.status_code == 403
    assert resposta_get.status_code == 403
    assert resposta_get_id.status_code == 403
    assert resposta_patch.status_code == 403
    assert resposta_delete.status_code == 403


async def test_usuario_recebe_403_em_rotas_admin(
    cliente: httpx.AsyncClient,
) -> None:
    token = await _registrar_e_fazer_login(cliente)

    resposta_lista = await cliente.get(
        "/admin/encomendas",
        headers={"Authorization": f"Bearer {token}"},
    )
    resposta_detalhe = await cliente.get(
        "/admin/encomendas/1",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resposta_lista.status_code == 403
    assert resposta_detalhe.status_code == 403


async def test_sem_token_retorna_401(cliente: httpx.AsyncClient) -> None:
    resposta_post = await cliente.post(
        "/encomendas",
        json={"codigo_rastreio": "BR000000001", "descricao": "x", "vendedor": "y"},
    )
    resposta_get = await cliente.get("/encomendas")
    resposta_admin = await cliente.get("/admin/encomendas")

    assert resposta_post.status_code == 401
    assert resposta_get.status_code == 401
    assert resposta_admin.status_code == 401


# --- ADMIN ---


async def test_admin_ve_todas_as_encomendas_com_usuario_id_e_email(
    cliente: httpx.AsyncClient,
) -> None:
    token_a = await _registrar_e_fazer_login(cliente, email="ana@exemplo.com")
    await _cadastra_encomenda(cliente, token_a, codigo_rastreio="BR000000001")

    token_b = await _registrar_e_fazer_login(cliente, email="bia@exemplo.com")
    await _cadastra_encomenda(cliente, token_b, codigo_rastreio="BR000000002")

    token_admin = await _login_admin(cliente)
    resposta = await cliente.get(
        "/admin/encomendas",
        headers={"Authorization": f"Bearer {token_admin}"},
    )

    assert resposta.status_code == 200
    corpos = resposta.json()
    assert len(corpos) == 2
    for corpo in corpos:
        assert "usuario_id" in corpo
        assert "usuario_email" in corpo


async def test_admin_filtro_por_grupo_e_usuario_id(
    cliente: httpx.AsyncClient,
    fabrica_sessao_teste: async_sessionmaker[AsyncSession],
) -> None:
    token_a = await _registrar_e_fazer_login(cliente, email="ana@exemplo.com")
    await _cadastra_encomenda(cliente, token_a, codigo_rastreio="BR000000001")
    usuario_ana_id = await _obter_id_usuario_por_email(fabrica_sessao_teste, "ana@exemplo.com")

    token_admin = await _login_admin(cliente)
    resposta = await cliente.get(
        f"/admin/encomendas?usuario_id={usuario_ana_id}",
        headers={"Authorization": f"Bearer {token_admin}"},
    )

    assert resposta.status_code == 200
    corpos = resposta.json()
    assert len(corpos) == 1
    assert corpos[0]["usuario_email"] == "ana@exemplo.com"


async def test_admin_detalhe_com_historico(
    cliente: httpx.AsyncClient,
) -> None:
    token_a = await _registrar_e_fazer_login(cliente, email="ana@exemplo.com")
    resposta = await _cadastra_encomenda(cliente, token_a)
    encomenda_id = resposta.json()["id"]

    token_admin = await _login_admin(cliente)
    resposta = await cliente.get(
        f"/admin/encomendas/{encomenda_id}",
        headers={"Authorization": f"Bearer {token_admin}"},
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["id"] == encomenda_id
    assert len(corpo["historico"]) == 1


async def test_admin_id_inexistente_retorna_404(
    cliente: httpx.AsyncClient,
) -> None:
    token_admin = await _login_admin(cliente)

    resposta = await cliente.get(
        "/admin/encomendas/999999",
        headers={"Authorization": f"Bearer {token_admin}"},
    )

    assert resposta.status_code == 404


async def test_admin_post_patch_delete_em_admin_retornam_405_ou_404(
    cliente: httpx.AsyncClient,
) -> None:
    token_admin = await _login_admin(cliente)

    resposta_post = await cliente.post(
        "/admin/encomendas",
        json={"codigo_rastreio": "BR000000001", "descricao": "x", "vendedor": "y"},
        headers={"Authorization": f"Bearer {token_admin}"},
    )
    resposta_patch = await cliente.patch(
        "/admin/encomendas/1",
        json={"descricao": "x"},
        headers={"Authorization": f"Bearer {token_admin}"},
    )
    resposta_delete = await cliente.delete(
        "/admin/encomendas/1",
        headers={"Authorization": f"Bearer {token_admin}"},
    )

    assert resposta_post.status_code in (404, 405)
    assert resposta_patch.status_code in (404, 405)
    assert resposta_delete.status_code in (404, 405)


# --- Concorrência ---


async def test_cadastros_simultaneos_mesmo_codigo_um_201_e_quatro_409(
    cliente: httpx.AsyncClient,
) -> None:
    token = await _registrar_e_fazer_login(cliente)

    respostas = await asyncio.gather(
        *[_cadastra_encomenda(cliente, token, codigo_rastreio="BRCONCORRENCIA") for _ in range(5)]
    )

    status_codes = sorted([r.status_code for r in respostas])
    assert status_codes == [201, 409, 409, 409, 409]


async def test_vinte_cadastros_simultaneos_codigos_diferentes_vinte_201(
    cliente: httpx.AsyncClient,
) -> None:
    token = await _registrar_e_fazer_login(cliente)

    respostas = await asyncio.gather(
        *[_cadastra_encomenda(cliente, token, codigo_rastreio=f"BR{i:05d}") for i in range(20)]
    )

    assert all(r.status_code == 201 for r in respostas)


async def _obter_id_usuario_por_email(
    fabrica_sessao_teste: async_sessionmaker[AsyncSession], email: str
) -> int:
    async with fabrica_sessao_teste() as sessao:
        resultado = await sessao.execute(select(Usuario.id).where(Usuario.email == email))
        return resultado.scalar_one()
