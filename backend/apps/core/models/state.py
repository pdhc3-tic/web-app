from django.db import models

class State(models.Model):
    id = models.AutoField(primary_key=True)
    sigla = models.CharField(max_length=2, unique=True)
    nome = models.CharField(max_length=255, unique=True)

    class Meta:
        verbose_name = 'Estado'
        verbose_name_plural = 'Estados'
        ordering = ['nome']

    def __str__(self):
        return f"{self.nome} ({self.sigla})"
