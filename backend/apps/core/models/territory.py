from django.db import models
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from .user import User
from .state import State



class Territory(models.Model):
    nome = models.CharField(max_length=255)
    estados = ArrayField(models.CharField(max_length=2), blank=True, default=list)
    articulador = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL, null=True, blank=True, related_name="territories_articulador")
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Território'
        verbose_name_plural = 'Territórios'
        ordering = ['nome']
        indexes = [
            models.Index(fields=['ativo']),
        ]


    def __str__(self):
        return self.nome

