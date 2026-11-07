from django.core.exceptions import ValidationError
from django.db import models
from django.conf import settings
from django.db.models import Q

from .role import Role


class ObjetoTipo(models.TextChoices):
    EVENTO = "evento", "Evento"
    EDITAL = "edital", "Edital"
    CANDIDATURA = "candidatura", "Candidatura"


OBJETO_DO_PERFIL_OPERACIONAL = {
    "coordenador-evento": ObjetoTipo.EVENTO,
    "credenciador": ObjetoTipo.EVENTO,
    "avaliador-selecao": ObjetoTipo.CANDIDATURA,
    "gestor-edital": ObjetoTipo.EDITAL,
}


def abrangencia_invalida(perfil, *, territorio_id, objeto_tipo, objeto_id) -> str | None:
    """A mensagem do erro, se houver. A trigger de `core_userprofile` garante o mesmo no banco, menos
    a coerência entre o perfil e o tipo do objeto."""
    if perfil.categoria != Role.Categoria.OPERACIONAL:
        if objeto_tipo is not None or objeto_id is not None:
            return f"O perfil {perfil.nome} é principal e não tem objeto de abrangência."
        return None
    if objeto_tipo is None or objeto_id is None:
        return f"O perfil {perfil.nome} é operacional e exige o objeto de abrangência."
    if territorio_id is not None:
        return f"O perfil {perfil.nome} é operacional: a abrangência é o objeto, não o território."
    esperado = OBJETO_DO_PERFIL_OPERACIONAL.get(perfil.slug)
    if esperado is not None and objeto_tipo != esperado:
        return f"O perfil {perfil.nome} se aplica a {esperado.label.lower()}."
    return None


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
    objeto_tipo = models.CharField(
        max_length=15, choices=ObjetoTipo.choices, null=True, blank=True, verbose_name="Tipo do objeto",
    )
    objeto_id = models.PositiveBigIntegerField(
        null=True, blank=True, verbose_name="ID do objeto",
        help_text="Referência sem FK: evento, edital ou candidatura designados ao perfil operacional.",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Perfil do Usuário"
        verbose_name_plural = "Perfis dos Usuários"
        ordering = ["user"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(objeto_tipo__isnull=True, objeto_id__isnull=True)
                    | Q(objeto_tipo__isnull=False, objeto_id__isnull=False)
                ),
                name="ck_userprofile_objeto_tipo_e_id_juntos",
            ),
            models.UniqueConstraint(
                fields=["user", "perfil", "objeto_tipo", "objeto_id"],
                condition=Q(objeto_tipo__isnull=False),
                name="uniq_userprofile_designacao_por_objeto",
            ),
        ]

    def clean(self):
        if self.perfil_id is None:
            return
        erro = abrangencia_invalida(
            self.perfil, territorio_id=self.territorio_id, objeto_tipo=self.objeto_tipo, objeto_id=self.objeto_id,
        )
        if erro:
            raise ValidationError(erro)

    def __str__(self):
        territorio_label = self.territorio or "Global"
        return f"{self.user} — {self.perfil} ({territorio_label})"
