import json

from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.db.models import signals
from django.dispatch import receiver


class TipoConfiguracao(models.TextChoices):
    STRING = "string", "String"
    INTEGER = "integer", "Integer"
    BOOLEAN = "boolean", "Boolean"
    JSON = "json", "JSON"


class SystemConfig(models.Model):
    chave = models.CharField(max_length=255, unique=True)
    valor = models.TextField()
    tipo = models.CharField(max_length=20, choices=TipoConfiguracao.choices)
    descricao = models.TextField(blank=True, default="")
    atualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="system_configs",
    )
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuração do Sistema"
        verbose_name_plural = "Configurações do Sistema"
        ordering = ["chave"]

    def __str__(self):
        return f"{self.chave}"


def _invalidate_system_config_cache(chave):
    cache.delete(f"system_config:{chave}")


@receiver(signals.pre_save, sender=SystemConfig)
def stash_system_config_old_value(sender, instance, **kwargs):
    if instance.pk:
        try:
            instance._old_valor = sender.objects.get(pk=instance.pk).valor
        except sender.DoesNotExist:
            instance._old_valor = None
    else:
        instance._old_valor = None


@receiver(signals.post_save, sender=SystemConfig)
def invalidate_system_config_cache_on_save(sender, instance, **kwargs):
    _invalidate_system_config_cache(instance.chave)


@receiver(signals.post_save, sender=SystemConfig)
def audit_system_config_update(sender, instance, created, **kwargs):
    if created:
        return

    old_valor = getattr(instance, "_old_valor", None)
    if old_valor == instance.valor:
        return

    from .audit_log import AuditLog

    AuditLog.objects.create(
        user=instance.atualizado_por,
        acao="system_config_update",
        modulo="core",
        entidade="SystemConfig",
        entidade_id=str(instance.pk),
        valores_anteriores={"valor": old_valor},
        valores_novos={"valor": instance.valor},
    )
