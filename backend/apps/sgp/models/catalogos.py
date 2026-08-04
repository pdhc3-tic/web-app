from django.db import models


class Cultura(models.Model):
    CATEGORIA_GRAOS = "graos"
    CATEGORIA_RAIZES = "raizes"
    CATEGORIA_FRUTAS = "frutas"
    CATEGORIA_HORTALICAS = "hortalicas"
    CATEGORIA_LEGUMINOSAS = "leguminosas"
    CATEGORIA_OLEAGINOSAS = "oleaginosas"
    CATEGORIA_FIBROSAS = "fibrosas"
    CATEGORIA_FORRAGEIRAS = "forrageiras"
    CATEGORIA_ORNAMENTAIS = "ornamentais"
    CATEGORIA_MEDICINAIS = "medicinais"
    CATEGORIA_OUTRAS = "outras"

    CATEGORIA_CHOICES = [
        (CATEGORIA_GRAOS, "Grãos"),
        (CATEGORIA_RAIZES, "Raízes"),
        (CATEGORIA_FRUTAS, "Frutas"),
        (CATEGORIA_HORTALICAS, "Hortaliças"),
        (CATEGORIA_LEGUMINOSAS, "Leguminosas"),
        (CATEGORIA_OLEAGINOSAS, "Oleaginosas"),
        (CATEGORIA_FIBROSAS, "Fibrosas"),
        (CATEGORIA_FORRAGEIRAS, "Forrageiras"),
        (CATEGORIA_ORNAMENTAIS, "Ornamentais"),
        (CATEGORIA_MEDICINAIS, "Medicinais"),
        (CATEGORIA_OUTRAS, "Outras"),
    ]

    CICLO_ANUAL = "anual"
    CICLO_PERENE = "perene"
    CICLO_BIANUAL = "bianual"

    CICLO_CHOICES = [
        (CICLO_ANUAL, "Anual"),
        (CICLO_PERENE, "Perene"),
        (CICLO_BIANUAL, "Bianual"),
    ]

    nome = models.CharField(max_length=120)
    nome_cientifico = models.CharField(max_length=160, blank=True, default="")
    categoria = models.CharField(max_length=30, choices=CATEGORIA_CHOICES)
    ciclo = models.CharField(max_length=10, choices=CICLO_CHOICES)
    ativa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Cultura"
        verbose_name_plural = "Culturas"
        ordering = ["categoria", "nome"]
        indexes = [
            models.Index(
                fields=["categoria", "nome"],
                name="idx_cultura_categoria_nome",
            ),
        ]

    def __str__(self):
        return self.nome


class EspecieAnimal(models.Model):
    CATEGORIA_BOVINO = "bovino"
    CATEGORIA_SUINO = "suino"
    CATEGORIA_OVINO = "ovino"
    CATEGORIA_CAPRINO = "caprino"
    CATEGORIA_AVES = "aves"
    CATEGORIA_EQUINO = "equino"
    CATEGORIA_PISCICULTURA = "piscicultura"
    CATEGORIA_APICULTURA = "apicultura"
    CATEGORIA_OUTROS = "outros"

    CATEGORIA_CHOICES = [
        (CATEGORIA_BOVINO, "Bovino"),
        (CATEGORIA_SUINO, "Suíno"),
        (CATEGORIA_OVINO, "Ovino"),
        (CATEGORIA_CAPRINO, "Caprino"),
        (CATEGORIA_AVES, "Aves"),
        (CATEGORIA_EQUINO, "Equino"),
        (CATEGORIA_PISCICULTURA, "Piscicultura"),
        (CATEGORIA_APICULTURA, "Apicultura"),
        (CATEGORIA_OUTROS, "Outros"),
    ]

    nome = models.CharField(max_length=120)
    categoria = models.CharField(max_length=30, choices=CATEGORIA_CHOICES)
    ativa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Espécie Animal"
        verbose_name_plural = "Espécies Animais"
        ordering = ["categoria", "nome"]
        indexes = [
            models.Index(
                fields=["categoria", "nome"],
                name="idx_especie_categoria_nome",
            ),
        ]

    def __str__(self):
        return self.nome
