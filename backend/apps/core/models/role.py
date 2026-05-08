class Role(models.Model):
    id = models.AutoField(primary_key=True)
    nome = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True)
    descricao = models.TextField(blank=True, null=True)
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return self.nome
    class Meta:
        verbose_name = 'Role'
        verbose_name_plural = 'Roles'
        ordering = ['nome']
