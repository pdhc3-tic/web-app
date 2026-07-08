from django.conf import settings
from django.db import models


class UPF(models.Model):
    projeto = models.ForeignKey(
        "sgp.Projeto",
        on_delete=models.CASCADE,
        related_name="upfs",
        verbose_name="Projeto",
    )
    comunidade = models.ForeignKey(
        "sgp.Comunidade",
        on_delete=models.PROTECT,
        related_name="upfs",
        null=True,
        blank=True,
        verbose_name="Comunidade",
    )

    nome_titular = models.CharField(
        max_length=255, verbose_name="Nome do Titular"
    )
    apelido = models.CharField(
        max_length=100, blank=True, default="", verbose_name="Apelido"
    )
    cpf = models.CharField(
        max_length=11, verbose_name="CPF", db_index=True
    )
    rg = models.CharField(
        max_length=20, blank=True, default="", verbose_name="RG"
    )
    data_nascimento = models.DateField(
        null=True, blank=True, verbose_name="Data de Nascimento"
    )
    genero = models.CharField(
        max_length=20,
        blank=True,
        default="",
        verbose_name="Gênero",
    )
    cor_raca = models.CharField(
        max_length=50,
        blank=True,
        default="",
        verbose_name="Cor/Raça",
    )
    estado_civil = models.CharField(
        max_length=20,
        blank=True,
        default="",
        verbose_name="Estado Civil",
    )
    escolaridade = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Escolaridade",
    )
    nacionalidade = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Nacionalidade",
    )
    naturalidade = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Naturalidade",
    )
    nome_mae = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Nome da Mãe",
    )
    nome_pai = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Nome do Pai",
    )

    telefone = models.CharField(
        max_length=20, blank=True, default="", verbose_name="Telefone"
    )
    whatsapp = models.CharField(
        max_length=20, blank=True, default="", verbose_name="WhatsApp"
    )
    celular = models.CharField(
        max_length=20, blank=True, default="", verbose_name="Celular"
    )
    email = models.EmailField(
        blank=True, default="", verbose_name="E-mail"
    )
    internet = models.BooleanField(
        default=False, verbose_name="Acesso à Internet"
    )
    dispositivo = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Dispositivo",
    )

    cep = models.CharField(
        max_length=8,
        blank=True,
        default="",
        verbose_name="CEP",
    )
    logradouro = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Logradouro",
    )
    numero = models.CharField(
        max_length=20,
        blank=True,
        default="",
        verbose_name="Número",
    )
    complemento = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Complemento",
    )
    bairro = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Bairro",
    )

    municipio = models.ForeignKey(
        "core.Municipality",
        on_delete=models.PROTECT,
        related_name="upfs",
        verbose_name="Município",
    )
    territorio = models.ForeignKey(
        "core.Territory",
        on_delete=models.PROTECT,
        related_name="upfs",
        verbose_name="Território",
    )

    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name="Latitude",
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name="Longitude",
    )

    pct = models.CharField(
        max_length=50,
        blank=True,
        default="",
        verbose_name="PCT",
    )
    posse_terra = models.CharField(
        max_length=50,
        blank=True,
        default="",
        verbose_name="Posse da Terra",
    )
    area_terra_ha = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Área da Terra (ha)",
    )
    situacao_moradia = models.CharField(
        max_length=50,
        blank=True,
        default="",
        verbose_name="Situação da Moradia",
    )
    tipo_moradia = models.CharField(
        max_length=50,
        blank=True,
        default="",
        verbose_name="Tipo de Moradia",
    )
    energia = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Energia",
    )
    agua = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Água",
    )

    numero_dap = models.CharField(
        max_length=30,
        blank=True,
        default="",
        verbose_name="Número DAP",
    )
    nis = models.CharField(
        max_length=11,
        blank=True,
        default="",
        verbose_name="NIS",
    )

    seguridade_social = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Seguridade Social",
    )

    foto_url = models.URLField(
        blank=True, default="", verbose_name="URL da Foto"
    )

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Criado por",
    )

    ativa = models.BooleanField(default=True, verbose_name="Ativa")
    criado_em = models.DateTimeField(
        auto_now_add=True, verbose_name="Criado em"
    )
    atualizado_em = models.DateTimeField(
        auto_now=True, verbose_name="Atualizado em"
    )

    class Meta:
        verbose_name = "UPF"
        verbose_name_plural = "UPFs"
        ordering = ["-criado_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["cpf", "projeto"],
                condition=models.Q(ativa=True),
                name="unique_cpf_ativo_por_projeto",
            ),
        ]
        indexes = [
            models.Index(fields=["municipio"], name="idx_upf_municipio"),
            models.Index(
                fields=["territorio"], name="idx_upf_territorio"
            ),
            models.Index(fields=["projeto"], name="idx_upf_projeto"),
            models.Index(fields=["cpf"], name="idx_upf_cpf"),
            models.Index(
                fields=["comunidade"], name="idx_upf_comunidade"
            ),
        ]

    def __str__(self):
        return f"{self.nome_titular} - {self.cpf}"
