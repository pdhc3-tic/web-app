from django.db import models
from django.conf import settings


class UserProfile(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profiles",
    )
    perfil = models.ForeignKey(
        "core.Role",
        on_delete=models.PROTECT,
        related_name="user_profiles",
        verbose_name="Perfil / Role",
    )
    territorio = models.ForeignKey(
        "core.Territory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user_profiles",
        help_text="Se nulo, acesso a todos os territórios do perfil.",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Perfil do Usuário"
        verbose_name_plural = "Perfis dos Usuários"
        ordering = ["user"]

    def __str__(self):
        territorio_label = self.territorio or "Global"
        return f"{self.user} — {self.perfil} ({territorio_label})"
