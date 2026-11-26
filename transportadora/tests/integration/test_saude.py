import httpx
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.banco_dados import obter_motor
from app.main import app


async def test_saude_retorna_200_e_servico_transportadora(
    cliente: httpx.AsyncClient,
) -> None:
    resposta = await cliente.get("/health")

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok", "servico": "transportadora"}


async def test_saude_retorna_503_quando_banco_nao_responde(
    cliente: httpx.AsyncClient,
) -> None:
    motor_invalido = create_async_engine(
        "postgresql+asyncpg://usuario_transportadora:troque-me@127.0.0.1:1/transportadora_teste"
    )
    app.dependency_overrides[obter_motor] = lambda: motor_invalido
    try:
        resposta = await cliente.get("/health")
    finally:
        app.dependency_overrides.pop(obter_motor, None)
        await motor_invalido.dispose()

    assert resposta.status_code == 503
    assert resposta.json() == {"status": "erro", "servico": "transportadora"}
