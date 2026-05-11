from django.db import models

class Role(models.Model):
    SLUG_CHOICES = [
        ('agricultor', 'Agricultor / Beneficiário'),
        ('adt-acr', 'ADT / ACR'),
        ('articulador-estadual', 'Articulador Estadual'),
        ('ugp', 'UGP — Coordenação'),
        ('fgd', 'FGD — Administrativo'),
        ('super-admin', 'Super Admin'),
    ]
    nome = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, choices=SLUG_CHOICES)
    descricao = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nome']
        verbose_name = 'Perfil'
        verbose_name_plural = 'Perfis'

    
    def __str__(self):
        return self.nome
