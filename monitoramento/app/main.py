from fastapi import FastAPI

app = FastAPI(title="HookLog Monitoramento")


@app.get("/health")
async def verificar_saude() -> dict[str, str]:
    return {"status": "ok", "servico": "monitoramento"}
