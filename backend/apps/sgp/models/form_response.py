from django.db import models


class FormResponse(models.Model):
    class Status(models.TextChoices):
        RASCUNHO = "rascunho", "Rascunho"
        SUBMETIDO = "submetido", "Submetido"

    class Origem(models.TextChoices):
        WEB = "web", "Web"
        SCA = "sca", "SCA"

    upf = models.ForeignKey(
        "sgp.UPF",
        on_delete=models.CASCADE,
        related_name="form_responses",
        verbose_name="UPF",
    )
    formulario_id = models.PositiveIntegerField(verbose_name="ID do formulário")
    formulario_nome = models.CharField(max_length=255, verbose_name="Nome do formulário")
    formulario_versao = models.CharField(max_length=50, verbose_name="Versão do formulário")
    data_preenchimento = models.DateTimeField(verbose_name="Data de preenchimento")
    respondente = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Respondente",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.RASCUNHO,
        verbose_name="Status",
    )
    respostas_json = models.JSONField(default=dict, verbose_name="Respostas")
    origem = models.CharField(
        max_length=10,
        choices=Origem.choices,
        default=Origem.WEB,
        verbose_name="Origem",
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")

    class Meta:
        verbose_name = "Resposta de formulário"
        verbose_name_plural = "Respostas de formulário"
        ordering = ["-data_preenchimento", "-pk"]
        indexes = [
            models.Index(
                fields=["upf", "-data_preenchimento"],
                name="idx_form_response_upf_data",
            ),
        ]

    def __str__(self):
        return f"{self.formulario_nome} - UPF {self.upf_id}"
