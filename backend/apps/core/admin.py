from django.contrib import admin

from .models import Comunidade, Estado, Municipio, Territorio


@admin.register(Estado)
class EstadoAdmin(admin.ModelAdmin):
    list_display = ("sigla", "nome")
    search_fields = ("sigla", "nome")


@admin.register(Territorio)
class TerritorioAdmin(admin.ModelAdmin):
    list_display = ("nome", "articulador", "ativo")
    list_filter = ("ativo",)
    search_fields = ("nome",)
    filter_horizontal = ("estados",)


@admin.register(Municipio)
class MunicipioAdmin(admin.ModelAdmin):
    list_display = ("nome", "estado", "territorio", "codigo_ibge")
    list_filter = ("estado", "territorio")
    search_fields = ("nome", "codigo_ibge")


@admin.register(Comunidade)
class ComunidadeAdmin(admin.ModelAdmin):
    list_display = ("nome", "municipio", "territorio", "zona")
    list_filter = ("zona", "territorio")
    search_fields = ("nome",)
