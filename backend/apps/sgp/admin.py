from django.contrib import admin

from .models import Comunidade


@admin.register(Comunidade)
class ComunidadeAdmin(admin.ModelAdmin):
    list_display = ('nome', 'municipio', 'ativa', 'criada_em', 'criada_por')
    list_filter = ('ativa', 'municipio__state')
    search_fields = ('nome',)
    readonly_fields = ('criada_em', 'criada_por')
