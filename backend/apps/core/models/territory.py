class Territory(models.Model):
    nome = models.CharField(max_length=255)
    estados = models.ManyToManyField(Estado, related_name="territorios", blank=True)
    articulador_id = models.ForeignKey(Articulador, on_delete=models.SET_NULL, null=True, blank=True, related_name="territorios")
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return str(self.nome)

    class Meta:
        verbose_name = 'Território'
        verbose_name_plural = 'Territórios'
        ordering = ['nome']


