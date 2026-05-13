from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import State, Territory, Municipality, User, Role
from apps.core.models.audit_log import AuditLog

# 1. NOVO: Admin para o model Role
@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("nome", "slug", "ativo", "criado_em")
    search_fields = ("nome", "slug")
    list_filter = ("ativo",)


# 2. ATUALIZADO: UserAdmin (trocando 'perfil' por 'role')
@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = (
        "email",
        "nome",
        "role",
        "ativo",
        "is_staff",
        "is_superuser",
        "ultimo_login",
    )
    list_filter = ("role", "ativo", "is_superuser")
    ordering = ("-ultimo_login",)
    search_fields = ("email", "nome")
    readonly_fields = ("ultimo_login",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Informações pessoais", {"fields": ("nome", "role")}),
        (
            "Permissões",
            {
                "fields": (
                    "ativo",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Datas importantes", {"fields": ("ultimo_login",)}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "nome",
                    "role",
                    "password1",
                    "password2",
                    "ativo",
                    "is_superuser",
                ),
            },
        ),
    )
    filter_horizontal = ("groups", "user_permissions")


# 3. ATUALIZADO: Estado -> State
@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ("sigla", "nome")
    search_fields = ("sigla", "nome")


# 4. ATUALIZADO: Territorio -> Territory
@admin.register(Territory)
class TerritoryAdmin(admin.ModelAdmin):
    list_display = ("nome", "articulador", "ativo")
    list_filter = ("ativo",)
    search_fields = ("nome",)
    # ATENÇÃO: Removido o filter_horizontal=("estados",) pois não funciona com ArrayField


# 5. ATUALIZADO: Municipio -> Municipality
@admin.register(Municipality)
class MunicipalityAdmin(admin.ModelAdmin):
    list_display = ("nome", "state", "territory", "codigo_ibge")
    list_filter = ("state", "territory")
    search_fields = ("nome", "codigo_ibge")

# 6. Audit Logs
@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["evento", "usuario", "ip", "criado_em"]
    readonly_fields = ["evento", "usuario", "detalhes", "ip", "criado_em"]