from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import State, Territory, Municipality, User, Role, UserProfile
from apps.core.models.audit_log import AuditLog


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name = "Perfil do Usuário"
    verbose_name_plural = "Perfil do Usuário"
    extra = 0


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("nome", "slug", "ativo", "criado_em")
    search_fields = ("nome", "slug")
    list_filter = ("ativo",)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    inlines = [UserProfileInline]
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


@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ("sigla", "nome")
    search_fields = ("sigla", "nome")


@admin.register(Territory)
class TerritoryAdmin(admin.ModelAdmin):
    list_display = ("nome", "articulador", "ativo")
    list_filter = ("ativo",)
    search_fields = ("nome",)


@admin.register(Municipality)
class MunicipalityAdmin(admin.ModelAdmin):
    list_display = ("nome", "state", "territory", "codigo_ibge")
    list_filter = ("state", "territory")
    search_fields = ("nome", "codigo_ibge")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """
    Admin de AuditLog em modo estritamente read-only.

    Nenhuma ação de criação, edição ou remoção está disponível,
    inclusive para superusuários. A imutabilidade é reforçada tanto
    aqui quanto pelo trigger PostgreSQL na camada de banco de dados.
    """

    list_display = ("timestamp", "usuario", "acao", "modulo", "entidade", "entidade_id", "ip")
    list_filter = ("acao", "modulo", "entidade")
    search_fields = ("user__email", "user__nome", "entidade", "entidade_id", "ip")
    ordering = ("-timestamp",)
    date_hierarchy = "timestamp"

    readonly_fields = (
        "usuario",
        "acao",
        "modulo",
        "entidade",
        "entidade_id",
        "valores_anteriores",
        "valores_novos",
        "ip",
        "user_agent",
        "timestamp",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "perfil", "territorio", "criado_em")
    list_filter = ("perfil", "territorio")
    search_fields = ("user__email", "user__nome")
    raw_id_fields = ("user",)