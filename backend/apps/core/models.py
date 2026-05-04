from django.db import models
from django.contrib.auth.models import User


class Estado(models.Model):
    SIGLA_CHOICES = [
        ("PE", "PE"),
        ("PB", "PB"),
        ("AL", "AL"),
        ("RN", "RN"),
        ("MA", "MA"),
        ("BA", "BA"),
        ("MG", "MG"),
    ]
    sigla = models.CharField(max_length=2, unique=True, choices=SIGLA_CHOICES)
    nome = models.CharField(max_length=100)

    def __str__(self) -> str:
        return str(self.sigla)


class Territorio(models.Model):
    nome = models.CharField(max_length=255)
    estados = models.ManyToManyField(Estado, related_name="territorios", blank=True)
    articulador = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="territorios",
    )
    ativo = models.BooleanField(default=True)

    def __str__(self) -> str:
        return str(self.nome)


class Municipio(models.Model):
    nome = models.CharField(max_length=255)
    estado = models.ForeignKey(
        Estado, on_delete=models.PROTECT, related_name="municipios"
    )
    territorio = models.ForeignKey(
        Territorio,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="municipios",
    )
    codigo_ibge = models.CharField(max_length=7, unique=True)
    area_km2 = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    populacao_total = models.PositiveIntegerField(null=True, blank=True)
    populacao_rural = models.PositiveIntegerField(null=True, blank=True)
    idh = models.DecimalField(max_digits=4, decimal_places=3, null=True, blank=True)
    perc_extremamente_pobres = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    benef_programa_agri_familiar = models.PositiveIntegerField(null=True, blank=True)
    estab_agri_familiar = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.nome} - {self.estado}"


class Comunidade(models.Model):
    ZONA_CHOICES = [
        ("rural", "Rural"),
        ("urbana", "Urbana"),
    ]
    nome = models.CharField(max_length=255)
    municipio = models.ForeignKey(
        Municipio, on_delete=models.PROTECT, related_name="comunidades"
    )
    territorio = models.ForeignKey(
        Territorio,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="comunidades",
    )
    lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    zona = models.CharField(max_length=10, choices=ZONA_CHOICES)

    def __str__(self) -> str:
        return str(self.nome)
