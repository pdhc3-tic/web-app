from django.db import models

# Perfis que enxergam o SGD de todos os territórios, sem recorte por estado.
PERFIS_NACIONAIS = frozenset({"super-admin", "ugp", "fgd"})


class Vinculo(models.TextChoices):
    SERVIDOR_UFERSA = "servidor_ufersa", "Servidor UFERSA"
    BOLSISTA = "bolsista", "Bolsista"
    COLABORADOR_EXTERNO = "colaborador_externo", "Colaborador externo"


class MeioTransporte(models.TextChoices):
    AEREO = "aereo", "Aéreo"
    RODOVIARIO = "rodoviario", "Rodoviário"
    PROPRIO = "proprio", "Próprio"
    OUTRO = "outro", "Outro"


class Classe(models.TextChoices):
    ECONOMICA = "economica", "Econômica"
    EXECUTIVA = "executiva", "Executiva"


class Urgencia(models.TextChoices):
    NORMAL = "normal", "Normal"
    URGENTE = "urgente", "Urgente"
    EMERGENCIAL = "emergencial", "Emergencial"


class TipoVeiculo(models.TextChoices):
    HATCH = "hatch", "Hatch"
    SEDAN = "sedan", "Sedã"
    SUV = "suv", "SUV"
    VAN = "van", "Van"
    MICRO_ONIBUS = "micro_onibus", "Micro-ônibus"
    ONIBUS = "onibus", "Ônibus"


class TipoMaterial(models.TextChoices):
    BANNER = "banner", "Banner"
    FOLDER = "folder", "Folder"
    CAMISETA = "camiseta", "Camiseta"
    BLOCO = "bloco", "Bloco"
    CANETA = "caneta", "Caneta"
    CHAPEU = "chapeu", "Chapéu"
    KIT_EVENTO = "kit_evento", "Kit evento"
    OUTRO = "outro", "Outro"


class TipoRefeicao(models.TextChoices):
    CAFE_MANHA = "cafe_manha", "Café da manhã"
    ALMOCO = "almoco", "Almoço"
    JANTAR = "jantar", "Jantar"
    COFFEE_BREAK = "coffee_break", "Coffee break"
    KIT_LANCHE = "kit_lanche", "Kit lanche"
    MARMITEX = "marmitex", "Marmitex"


# Códigos IBGE das 26 capitais estaduais e de Brasília. Município fora do
# enquadramento explícito de uma faixa de diária cai em "demais capitais" se
# estiver aqui, ou em "demais localidades" (Decreto 5.992/2006, anexo).
CODIGOS_IBGE_CAPITAIS = frozenset({
    "1100205",  # Porto Velho/RO
    "1200401",  # Rio Branco/AC
    "1302603",  # Manaus/AM
    "1400100",  # Boa Vista/RR
    "1501402",  # Belém/PA
    "1600303",  # Macapá/AP
    "1721000",  # Palmas/TO
    "2111300",  # São Luís/MA
    "2211001",  # Teresina/PI
    "2304400",  # Fortaleza/CE
    "2408102",  # Natal/RN
    "2507507",  # João Pessoa/PB
    "2611606",  # Recife/PE
    "2704302",  # Maceió/AL
    "2800308",  # Aracaju/SE
    "2927408",  # Salvador/BA
    "3106200",  # Belo Horizonte/MG
    "3205309",  # Vitória/ES
    "3304557",  # Rio de Janeiro/RJ
    "3550308",  # São Paulo/SP
    "4106902",  # Curitiba/PR
    "4205407",  # Florianópolis/SC
    "4314902",  # Porto Alegre/RS
    "5002704",  # Campo Grande/MS
    "5103403",  # Cuiabá/MT
    "5208707",  # Goiânia/GO
    "5300108",  # Brasília/DF
})
