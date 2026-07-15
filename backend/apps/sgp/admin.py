from django.contrib import admin

from apps.sgp.models import (
    Comunidade,
    MembroFamilia,
    Projeto,
    UPF,
)


@admin.register(Projeto)
class ProjetoAdmin(admin.ModelAdmin):
    list_display = ["nome", "ativo", "criado_em"]
    list_filter = ["ativo"]
    search_fields = ["nome"]


@admin.register(UPF)
class UPFAdmin(admin.ModelAdmin):
    list_display = [
        "get_nome_titular", "get_cpf", "projeto",
        "municipio", "territorio", "ativa", "criado_em",
    ]
    list_filter = ["ativa", "projeto", "territorio"]
    search_fields = ["titular__nome_completo", "titular__cpf"]
    readonly_fields = [
        "territorio", "criado_em", "atualizado_em", "criado_por",
    ]

    def get_nome_titular(self, obj):
        return obj.titular.nome_completo
    get_nome_titular.short_description = "Titular"

    def get_cpf(self, obj):
        return obj.titular.cpf
    get_cpf.short_description = "CPF"


@admin.register(MembroFamilia)
class MembroFamiliaAdmin(admin.ModelAdmin):
    list_display = [
        "nome_completo", "parentesco", "upf", "cpf", "criado_em",
    ]
    list_filter = ["parentesco"]
    search_fields = ["nome_completo", "cpf"]


@admin.register(Comunidade)
class ComunidadeAdmin(admin.ModelAdmin):
    list_display = ('nome', 'municipio', 'ativa', 'criada_em', 'criada_por')
    list_filter = ('ativa', 'municipio__state')
    search_fields = ('nome',)
    readonly_fields = ('criada_em', 'criada_por')
