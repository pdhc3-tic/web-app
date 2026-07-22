from django.contrib import admin

from apps.sgp.models import (
    Comunidade,
    Cultura,
    EspecieAnimal,
    MembroFamilia,
    Production,
    Projeto,
    UPF,
    WorkPlanAcao,
    WorkPlanMeta,
)


@admin.register(Projeto)
class ProjetoAdmin(admin.ModelAdmin):
    list_display = ["nome", "ativo", "criado_em"]
    list_filter = ["ativo"]
    search_fields = ["nome"]


@admin.register(Cultura)
class CulturaAdmin(admin.ModelAdmin):
    list_display = ["nome", "nome_cientifico", "categoria", "ciclo", "ativa"]
    list_filter = ["ativa", "categoria", "ciclo"]
    search_fields = ["nome", "nome_cientifico"]


@admin.register(EspecieAnimal)
class EspecieAnimalAdmin(admin.ModelAdmin):
    list_display = ["nome", "categoria", "ativa"]
    list_filter = ["ativa", "categoria"]
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


@admin.register(Production)
class ProductionAdmin(admin.ModelAdmin):
    list_display = ["upf", "tipo", "cultura", "especie", "tipo_outra", "criado_em"]
    list_filter = ["tipo", "sistema_criacao", "tipo_outra"]
    search_fields = [
        "upf__titular__nome_completo",
        "cultura__nome",
        "especie__nome",
        "descricao_outra",
    ]
    readonly_fields = ["criado_em", "atualizado_em"]


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


class WorkPlanAcaoInline(admin.TabularInline):
    model = WorkPlanAcao
    extra = 0
    fields = [
        "numero", "descricao", "tipo_unidade",
        "quantidade_planejada", "valor_unitario", "valor_total",
        "status_execucao",
    ]
    readonly_fields = ["valor_total", "status_execucao"]


@admin.register(WorkPlanMeta)
class WorkPlanMetaAdmin(admin.ModelAdmin):
    list_display = [
        "numero", "titulo", "data_inicio", "data_fim",
        "valor_total_planejado", "status_calculado", "criado_em",
    ]
    list_filter = ["numero"]
    search_fields = ["titulo"]
    readonly_fields = [
        "valor_total_planejado", "status_calculado",
        "criado_por", "criado_em", "atualizado_em",
    ]
    inlines = [WorkPlanAcaoInline]


@admin.register(WorkPlanAcao)
class WorkPlanAcaoAdmin(admin.ModelAdmin):
    list_display = [
        "meta", "numero", "descricao", "tipo_unidade",
        "quantidade_planejada", "valor_total", "status_execucao",
    ]
    list_filter = ["meta"]
    search_fields = ["descricao"]
    readonly_fields = ["valor_total", "status_execucao"]
