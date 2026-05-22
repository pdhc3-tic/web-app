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


@receiver(signals.post_save, sender=SystemConfig)
def invalidate_system_config_cache_on_save(sender, instance, **kwargs):
    _invalidate_system_config_cache(instance.chave)
