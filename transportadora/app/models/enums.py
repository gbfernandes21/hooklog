from enum import Enum


class Papel(str, Enum):
    USER = "USER"
    ADMIN = "ADMIN"


class StatusRemessa(str, Enum):
    AGUARDANDO_ENVIO = "AGUARDANDO_ENVIO"
    POSTADO = "POSTADO"
    EM_TRANSITO = "EM_TRANSITO"
    SAIU_PARA_ENTREGA = "SAIU_PARA_ENTREGA"
    ENTREGUE = "ENTREGUE"


class EstadoEnvio(str, Enum):
    PENDENTE = "PENDENTE"
    ENVIADO = "ENVIADO"
    FALHA = "FALHA"
