class State(models.Model):
    id = models.AutoField(primary_key=True)
    sigla = models.CharField(max_length=2, unique=True)
    nome = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.nome
    class Meta:
        verbose_name = 'State'
        verbose_name_plural = 'States'
        ordering = ['nome']
