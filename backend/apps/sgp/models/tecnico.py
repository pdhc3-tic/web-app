from django.conf import settings
from django.db import models


class Tecnico(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tecnico",
        verbose_name="Usuário",
    )
    territorio = models.ForeignKey(
        "core.Territory",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="tecnicos",
        verbose_name="Território",
        help_text="Se nulo, acesso a todos os territórios.",
    )
    osc = models.ForeignKey(
        "core.Organization",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="tecnicos",
        verbose_name="OSC",
    )
    papel = models.CharField(max_length=100, verbose_name="Papel")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")

    class Meta:
        verbose_name = "Técnico"
        verbose_name_plural = "Técnicos"
        ordering = ["user__nome"]
        indexes = [
            models.Index(fields=["territorio"], name="idx_tecnico_territorio"),
            models.Index(fields=["osc"], name="idx_tecnico_osc"),
            models.Index(fields=["ativo"], name="idx_tecnico_ativo"),
        ]

    def __str__(self):
        return f"{self.user.nome} - {self.papel}"
