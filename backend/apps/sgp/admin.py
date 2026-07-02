from django.contrib import admin

from apps.sgp.models import Projeto, UPF


@admin.register(Projeto)
class ProjetoAdmin(admin.ModelAdmin):
    list_display = ["nome", "ativo", "criado_em"]
    list_filter = ["ativo"]
    search_fields = ["nome"]


@admin.register(UPF)
class UPFAdmin(admin.ModelAdmin):
    list_display = [
        "nome_titular",
        "cpf",
        "projeto",
        "municipio",
        "territorio",
        "ativa",
        "criado_em",
    ]
    list_filter = ["ativa", "projeto", "territorio"]
    search_fields = ["nome_titular", "cpf"]
    readonly_fields = ["territorio", "criado_em", "atualizado_em", "criado_por"]
