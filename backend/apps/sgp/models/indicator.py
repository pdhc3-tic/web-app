"""Catálogo institucional de Indicadores (SGP §5.4).

Cada Ação do Plano de Trabalho é medida por um Indicador; Ações de Metas e
Submetas diferentes podem compartilhar o mesmo, o que permite consolidar a
mesma unidade de entrega em todo o projeto.
"""
from django.conf import settings
from django.db import models

UNIDADE_MEDIDA_CHOICES = [
    ("unidade", "Unidade"),
    ("familia", "Família"),
    ("pessoa", "Pessoa"),
    ("evento", "Evento"),
    ("plano", "Plano"),
    ("relatorio", "Relatório"),
    ("hectare", "Hectare"),
    ("outro", "Outro"),
]

FORMA_CONTAGEM_ATIVIDADES = "contagem_atividades"
FORMA_SOMA_UFPAS = "soma_ufpas"
FORMA_SOMA_PARTICIPANTES = "soma_participantes"
FORMA_MANUAL = "manual"

FORMA_APURACAO_CHOICES = [
    (FORMA_CONTAGEM_ATIVIDADES, "Contagem de atividades concluídas"),
    (FORMA_SOMA_UFPAS, "Soma de UFPAs vinculadas"),
    (FORMA_SOMA_PARTICIPANTES, "Soma de participantes"),
    (FORMA_MANUAL, "Lançamento manual pela UGP"),
]

CATEGORIA_CHOICES = [
    ("formacao", "Formação"),
    ("assistencia_tecnica", "Assistência técnica"),
    ("estruturacao_produtiva", "Estruturação produtiva"),
    ("gestao", "Gestão"),
    ("outro", "Outro"),
]

DESAGREGACAO_CHOICES = [
    ("genero", "Gênero"),
    ("geracao", "Geração"),
    ("pct", "PCT"),
    ("territorio", "Território"),
]


class Indicator(models.Model):
    codigo = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Código",
        help_text="Identificador curto e estável (ex: IND-OFI).",
    )
    nome = models.CharField(max_length=255, verbose_name="Nome")
    unidade_medida = models.CharField(
        max_length=20, choices=UNIDADE_MEDIDA_CHOICES, verbose_name="Unidade de medida"
    )
    forma_apuracao = models.CharField(
        max_length=20, choices=FORMA_APURACAO_CHOICES, verbose_name="Forma de apuração"
    )
    categoria = models.CharField(
        max_length=30,
        choices=CATEGORIA_CHOICES,
        blank=True,
        default="",
        verbose_name="Categoria",
    )
    ods_ids = models.JSONField(
        default=list,
        blank=True,
        verbose_name="ODS",
        help_text="Lista de IDs dos Objetivos de Desenvolvimento Sustentável (1–17).",
    )
    desagregacoes = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Desagregação exigida",
        help_text="Recortes que o relatório do Indicador deve produzir.",
    )
    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo",
        help_text="Inativo não pode ser vinculado a novas Ações, mas preserva o histórico.",
    )

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Criado por",
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Indicador"
        verbose_name_plural = "Indicadores"
        ordering = ["codigo"]
        indexes = [
            models.Index(fields=["ativo"], name="idx_indicator_ativo"),
        ]

    def __str__(self):
        return f"{self.codigo} – {self.nome}"
