from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Comunidade, Estado, Municipio, Territorio, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = (
        "email",
        "nome",
        "perfil",
        "ativo",
        "is_staff",
        "is_superuser",
        "ultimo_login",
        "date_joined",
    )
    list_filter = ("perfil", "ativo", "is_staff", "is_superuser")
    ordering = ("-date_joined",)
    search_fields = ("email", "nome")
    readonly_fields = ("ultimo_login", "date_joined")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Informações pessoais", {"fields": ("nome", "perfil")}),
        (
            "Permissões",
            {
                "fields": (
                    "ativo",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Datas importantes", {"fields": ("ultimo_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "nome",
                    "perfil",
                    "password1",
                    "password2",
                    "ativo",
                    "is_staff",
                    "is_superuser",
                ),
            },
        ),
    )
    filter_horizontal = ("groups", "user_permissions")


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

