from django.conf import settings
from django.db import models
from django.db.models import Q


class Comunidade(models.Model):
    id = models.AutoField(primary_key=True)
    nome = models.CharField(max_length=255)
    municipio = models.ForeignKey(
        'core.Municipality',
        on_delete=models.PROTECT,
        related_name='comunidades',
    )
    lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    ativa = models.BooleanField(default=True)
    criada_em = models.DateTimeField(auto_now_add=True)
    criada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='comunidades_criadas',
    )

    class Meta:
        verbose_name = 'Comunidade'
        verbose_name_plural = 'Comunidades'
        ordering = ['nome']
        indexes = [
            models.Index(fields=['municipio']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['nome', 'municipio'],
                condition=Q(ativa=True),
                name='unique_comunidade_ativa_por_municipio',
            ),
        ]

    def __str__(self):
        return f"{self.nome} - {self.municipio.nome}/{self.municipio.state.sigla}"
