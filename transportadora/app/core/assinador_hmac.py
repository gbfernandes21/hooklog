import hashlib
import hmac


def assinar(segredo: str, carimbo_tempo: int, corpo_bruto: bytes) -> dict[str, str]:
    conteudo_assinado = f"{carimbo_tempo}.".encode() + corpo_bruto
    resumo = hmac.new(segredo.encode(), conteudo_assinado, hashlib.sha256).hexdigest()

    return {
        "X-Carimbo-Tempo": str(carimbo_tempo),
        "X-Assinatura": f"sha256={resumo}",
    }
