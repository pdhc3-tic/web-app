from django.db import models

class Municipality(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    estado_id = models.ForeignKey(State, on_delete=models.CASCADE, related_name="municipalities")
    territorio_id = models.ForeignKey(Territorio, on_delete=models.SET_NULL, null=True, blank=True, related_name="municipalities")
    codigo_ibge = models.CharField(max_length=7, unique=True)
    area_km2 = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    pop_total = models.IntegerField(null=True, blank=True)
    idh = models.DecimalField(max_digits=4, decimal_places=3, null=True, blank=True)
    perc_extrem_pobreza = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    benef_programa_agri_familiar = models.IntegerField(null=True, blank=True)
    estab_agri_familiar = models.IntegerField(null=True, blank=True)

    class Meta:
        verbose_name = 'Municipality'
        verbose_name_plural = 'Municipalities'
        ordering = ['name']
        indexes = [
            models.Index(fields=['territorio_id']),
            # codigo_ibge já cria um índice por ser unique
        ]

    def __str__(self):
        return f"{self.nome} - {self.state.sigla}"

