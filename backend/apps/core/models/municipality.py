from django.db import models

class Municipality(models.Model):
    id = models.AutoField(primary_key=True)
    nome = models.CharField(max_length=255)
    state = models.ForeignKey('core.State', on_delete=models.CASCADE, related_name='municipalities')
    territory = models.ForeignKey('core.Territory', on_delete=models.SET_NULL, null=True, blank=True, related_name='municipalities')
    codigo_ibge = models.CharField(max_length=7, unique=True)
    area_km2 = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    pop_total = models.IntegerField(null=True, blank=True)
    pop_rural = models.IntegerField(null=True, blank=True)
    idh = models.DecimalField(max_digits=4, decimal_places=3, null=True, blank=True)
    perc_extr_pobres = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    benef_programa_agri_familiar = models.IntegerField(null=True, blank=True)
    estab_agri_familiar = models.IntegerField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Município'
        verbose_name_plural = 'Municípios'
        ordering = ['nome']
        indexes = [
            models.Index(fields=['territory']),
            models.Index(fields=['codigo_ibge']),
        ]

    def __str__(self):
        return f"{self.nome} - {self.state.sigla}"

