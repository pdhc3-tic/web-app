from django.db import models


class Projeto(models.Model):
    nome = models.CharField(max_length=255, verbose_name="Nome do Projeto")
    descricao = models.TextField(blank=True, default="", verbose_name="Descrição")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Projeto"
        verbose_name_plural = "Projetos"
        ordering = ["nome"]

    def __str__(self):
        return self.nome
