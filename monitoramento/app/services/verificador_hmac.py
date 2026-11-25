import hashlib
import hmac
from datetime import datetime

PREFIXO_ASSINATURA = "sha256="


def verificar(
    segredo: str,
    carimbo_tempo: str,
    assinatura: str,
    corpo_bruto: bytes,
    agora: datetime,
    tolerancia_segundos: int,
) -> bool:
    try:
        carimbo = int(carimbo_tempo)
    except (TypeError, ValueError):
        return False

    if abs(agora.timestamp() - carimbo) > tolerancia_segundos:
        return False

    if not assinatura.startswith(PREFIXO_ASSINATURA):
        return False

    resumo_informado = assinatura[len(PREFIXO_ASSINATURA) :]
    conteudo_assinado = f"{carimbo_tempo}.".encode() + corpo_bruto
    resumo_esperado = hmac.new(segredo.encode(), conteudo_assinado, hashlib.sha256).hexdigest()

    return hmac.compare_digest(resumo_esperado, resumo_informado)
