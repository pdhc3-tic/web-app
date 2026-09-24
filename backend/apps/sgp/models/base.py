"""
SoftDeleteModel — Issue #267

Base abstrata para uniformizar o soft-delete dos models que hoje usam
convenções divergentes (`ativa`/`ativo`). O manager padrão (`objects`)
já exclui os inativos, tornando o filtro implícito; `all_objects` mantém
acesso completo para os casos que precisam ver o histórico (admin,
endpoint de histórico da UPF).
"""
from django.db import models
from django.utils import timezone


class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(ativo=True)


class SoftDeleteModel(models.Model):
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name="Desativado em")

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True
        # `_base_manager` (usado por refresh_from_db(), pela coleta de cascade
        # delete e por acesso a relações reversas sem queryset explícito)
        # precisa enxergar tudo — só `_default_manager` (`objects`, primeiro
        # declarado) deve filtrar os inativos. Concretas devem herdar via
        # `class Meta(SoftDeleteModel.Meta):` para propagar esta opção.
        base_manager_name = "all_objects"

    def soft_delete(self):
        self.ativo = False
        self.deleted_at = timezone.now()
        self.save(update_fields=["ativo", "deleted_at"])
