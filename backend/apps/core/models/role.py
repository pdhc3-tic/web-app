from django.db import models

class Role(models.Model):
    class Categoria(models.TextChoices):
        PRINCIPAL = "principal", "Principal"
        OPERACIONAL = "operacional", "Operacional"

    SLUG_CHOICES = [
        ('agricultor', 'Agricultor / Beneficiário'),
        ('adt-acr', 'ADT / ACR'),
        ('articulador-estadual', 'Articulador Estadual'),
        ('ugp', 'UGP — Coordenação'),
        ('fgd', 'FGD — Administrativo'),
        ('super-admin', 'Super Admin'),
        ('coordenador-evento', 'Coordenador de Evento'),
        ('credenciador', 'Credenciador'),
        ('avaliador-selecao', 'Avaliador de Seleção'),
        ('gestor-edital', 'Gestor de Edital'),
    ]
    nome = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, choices=SLUG_CHOICES)
    descricao = models.TextField(blank=True)
    categoria = models.CharField(max_length=15, choices=Categoria.choices, default=Categoria.PRINCIPAL)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nome']
        verbose_name = 'Perfil'
        verbose_name_plural = 'Perfis'


    def __str__(self):
        return self.nome
