from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import State, Territory, Municipality, User, Role, UserProfile, Organization
from .models.notifications import Notification, NotificationPreference
from .models.system_config import SystemConfig
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

    list_display = ("timestamp", "user", "acao", "modulo", "entidade", "entidade_id", "ip")
    list_filter = ("acao", "modulo", "entidade")
    search_fields = ("user__email", "user__nome", "entidade", "entidade_id", "ip")
    ordering = ("-timestamp",)
    date_hierarchy = "timestamp"

    readonly_fields = (
        "user",
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


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("titulo", "user", "tipo", "status", "enviado_em", "lido_em")
    list_filter = ("tipo", "status")
    search_fields = ("titulo", "user__email")
    raw_id_fields = ("user",)
    readonly_fields = ("enviado_em",)


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "tipo_evento", "canal", "ativo")
    list_filter = ("canal", "ativo")
    search_fields = ("user__email", "tipo_evento")
    raw_id_fields = ("user",)


@admin.register(SystemConfig)
class SystemConfigAdmin(admin.ModelAdmin):
    list_display = ("chave", "tipo", "descricao", "atualizado_por", "atualizado_em")
    list_filter = ("tipo",)
    search_fields = ("chave", "descricao")
    readonly_fields = ("chave", "tipo", "atualizado_em")


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("nome", "cnpj", "tipo", "municipio", "ativa")
    list_filter = ("municipio__state", "tipo", "ativa")
    search_fields = ("nome", "cnpj")
    filter_horizontal = ("territorios",)
    raw_id_fields = ("municipio",)