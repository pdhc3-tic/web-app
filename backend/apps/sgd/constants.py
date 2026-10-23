from django.db import models


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
