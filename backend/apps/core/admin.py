import functools

from django import forms
from django.db import router, transaction
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.core.exceptions import PermissionDenied
from django.forms.models import BaseInlineFormSet
from django.utils.html import format_html_join
from django.urls import reverse

from rest_framework.exceptions import ValidationError

from apps.sgd.exceptions import TransicaoInvalida

from .models import State, Territory, Municipality, User, Role, UserProfile, Organization
from .models.notifications import Notification, NotificationPreference
from .models.system_config import SystemConfig
from .models import AuditLog
from .services.parametros import parametro_do_orcamento_invalido, valor_do_tipo
from .services.usuarios import (
    SUPER_ADMIN, desativar, exigir_super_admin_restante, sobra_super_admin, travar_ultimo_super_admin,
)


def _mensagem(erro: ValidationError) -> str:
    detalhe = erro.detail
    grupos = detalhe.values() if isinstance(detalhe, dict) else [detalhe]
    return " ".join(
        str(mensagem) for grupo in grupos for mensagem in (grupo if isinstance(grupo, list) else [grupo])
    )


def _exigir_no_formulario(**removidos) -> None:
    """A conferência com trava, como erro de formulário. O Admin salva numa transação, então a trava vale
    até o commit, e vem antes de gravar qualquer linha de usuário."""
    try:
        exigir_super_admin_restante(**removidos)
    except ValidationError as exc:
        raise forms.ValidationError(_mensagem(exc)) from exc


def _exigir_na_exclusao(**removidos) -> None:
    """Mesma conferência na exclusão, que não tem formulário: o botão já some sem outro Super Admin, e
    isto cobre o pedido que chega junto com outro."""
    try:
        exigir_super_admin_restante(**removidos)
    except ValidationError as exc:
        raise PermissionDenied(_mensagem(exc)) from exc


def _travar_antes_do_registro(request) -> None:
    """O Django grava o registro da exclusão, com FK para quem exclui, antes de `delete_model` e
    `delete_queryset`. A trava do último Super Admin vem antes desse registro: duas pessoas excluindo uma
    à outra ao mesmo tempo, com a trava depois, esperariam uma pela outra até o banco abortar uma delas.
    Quem exclui é conferido já com a trava: se foi excluído ou desativado enquanto esperava, para aqui."""
    travar_ultimo_super_admin()
    if not User.objects.filter(pk=getattr(request.user, "pk", None), ativo=True).exists():
        raise PermissionDenied("Sua conta foi desativada ou excluída.")


def _exclusao_em_lote_atomica(acoes):
    """As ações do Admin rodam sem a transação que ele abre na edição: o registro da exclusão e a exclusão
    entram ou saem juntos, e a trava do último Super Admin vale até o commit."""
    if "delete_selected" in acoes:
        funcao, nome, descricao = acoes["delete_selected"]

        @functools.wraps(funcao)
        def excluir_selecionados(modeladmin, request, queryset):
            with transaction.atomic(using=router.db_for_write(modeladmin.model)):
                _travar_antes_do_registro(request)
                return funcao(modeladmin, request, queryset)

        acoes["delete_selected"] = (excluir_selecionados, nome, descricao)
    return acoes


class ExclusaoComTravaMixin:
    """Exclusão unitária e em lote com a trava do último Super Admin pega antes do registro da exclusão."""

    def delete_view(self, request, object_id, extra_context=None):
        if request.method != "POST":
            return super().delete_view(request, object_id, extra_context)
        with transaction.atomic(using=router.db_for_write(self.model)):
            _travar_antes_do_registro(request)
            return super().delete_view(request, object_id, extra_context)

    def get_actions(self, request):
        return _exclusao_em_lote_atomica(super().get_actions(request))


class UserProfileFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        usuario = self.instance
        if usuario.pk is None or self._continua_super_admin():
            return
        _exigir_no_formulario(sem_usuarios=[usuario.pk])

    def _continua_super_admin(self) -> bool:
        return any(
            getattr(form.cleaned_data.get("perfil"), "slug", None) == SUPER_ADMIN
            and not form.cleaned_data.get("DELETE")
            for form in self.forms
        )


class UserProfileInline(admin.TabularInline):
    model = UserProfile
    formset = UserProfileFormSet
    verbose_name = "Perfil"
    verbose_name_plural = "Perfis"
    extra = 1
    fields = ("perfil", "territorio", "objeto_tipo", "objeto_id")


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("nome", "slug", "categoria", "ativo", "criado_em")
    search_fields = ("nome", "slug")
    list_filter = ("ativo", "categoria")
    readonly_fields = ("categoria",)


@admin.register(User)
class UserAdmin(ExclusaoComTravaMixin, DjangoUserAdmin):
    inlines = [UserProfileInline]
    list_display = (
        "email",
        "nome",
        "perfis_resumo",
        "ativo",
        "is_staff",
        "is_superuser",
        "ultimo_login",
    )
    list_filter = ("ativo", "is_superuser", "profiles__perfil")
    ordering = ("-ultimo_login",)
    search_fields = ("email", "nome")
    readonly_fields = ("ultimo_login",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Informações pessoais", {"fields": ("nome",)}),
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
                    "password1",
                    "password2",
                    "ativo",
                    "is_superuser",
                ),
            },
        ),
    )
    filter_horizontal = ("groups", "user_permissions")

    def save_model(self, request, obj, form, change):
        if not change:
            super().save_model(request, obj, form, change)
            return
        # A conta foi lida sem trava. Regravar a linha inteira devolveria o `ativo` dessa leitura por cima
        # de uma ativação ou desativação concorrente, sem passar pela regra do último Super Admin. Por isso
        # só o que o formulário mudou é gravado, e `ativo` só na reativação.
        mudou_ativo = "ativo" in form.changed_data
        reativando = mudou_ativo and obj.ativo
        if mudou_ativo and not obj.ativo:
            # `desativar` relê `ativo` com a linha travada e grava só essa coluna. Os outros campos vão
            # depois: trocar o e-mail, coluna única, barra a checagem de FK de quem segura o limite que o
            # cancelamento precisa.
            try:
                desativar(obj, por=request.user)
            except TransicaoInvalida as exc:
                obj.ativo = True
                self.message_user(request, f"Usuário não desativado: {exc.mensagem}", level=messages.ERROR)
            except ValidationError as exc:
                obj.ativo = True
                self.message_user(request, f"Usuário não desativado: {_mensagem(exc)}", level=messages.ERROR)
        campos = [
            campo.name for campo in obj._meta.concrete_fields
            if campo.name in form.changed_data and (campo.name != "ativo" or reativando)
        ]
        if campos:
            obj.save(update_fields=campos)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and not sobra_super_admin(sem_usuarios=[obj.pk]):
            return False
        return super().has_delete_permission(request, obj)

    def delete_model(self, request, obj):
        _exigir_na_exclusao(sem_usuarios=[obj.pk])
        super().delete_model(request, obj)

    @transaction.atomic
    def delete_queryset(self, request, queryset):
        _exigir_na_exclusao(sem_usuarios=list(queryset.values_list("pk", flat=True)))
        super().delete_queryset(request, queryset)

    def perfis_resumo(self, obj):
        profiles = obj.profiles.select_related("perfil", "territorio").all()
        items = []
        for p in profiles:
            label = p.perfil.nome
            if p.territorio:
                label += f" ({p.territorio.nome})"
            items.append(label)
        return ", ".join(items) if items else "—"
    perfis_resumo.short_description = "Perfis"


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


class UserProfileAdminForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = "__all__"

    def clean(self):
        dados = super().clean()
        # Antes de `_post_clean`: `self.instance` ainda tem o perfil e o usuário gravados.
        vinculo = self.instance
        if self.errors or vinculo.pk is None:
            return dados
        if getattr(dados.get("perfil"), "slug", None) != SUPER_ADMIN or dados.get("user") != vinculo.user:
            _exigir_no_formulario(sem_vinculos=[vinculo.pk])
        return dados


@admin.register(UserProfile)
class UserProfileAdmin(ExclusaoComTravaMixin, admin.ModelAdmin):
    form = UserProfileAdminForm
    list_display = ("user", "perfil", "territorio", "criado_em")
    list_filter = ("perfil", "territorio")
    search_fields = ("user__email", "user__nome")
    raw_id_fields = ("user",)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and not sobra_super_admin(sem_vinculos=[obj.pk]):
            return False
        return super().has_delete_permission(request, obj)

    def delete_model(self, request, obj):
        _exigir_na_exclusao(sem_vinculos=[obj.pk])
        super().delete_model(request, obj)

    @transaction.atomic
    def delete_queryset(self, request, queryset):
        _exigir_na_exclusao(sem_vinculos=list(queryset.values_list("pk", flat=True)))
        super().delete_queryset(request, queryset)


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


class SystemConfigAdminForm(forms.ModelForm):
    """Mesmas regras do `PATCH /system-config/{chave}/`: o tipo e, nos parâmetros do orçamento, as opções e
    faixas. O Admin salva numa transação, que segura a trava dos limiares do semáforo."""

    class Meta:
        model = SystemConfig
        fields = "__all__"

    def clean_valor(self):
        try:
            valor = valor_do_tipo(self.instance.tipo, self.cleaned_data["valor"])
        except ValidationError as exc:
            raise forms.ValidationError(_mensagem(exc)) from exc
        erro = parametro_do_orcamento_invalido(self.instance.chave, valor)
        if erro:
            raise forms.ValidationError(erro)
        return valor


@admin.register(SystemConfig)
class SystemConfigAdmin(admin.ModelAdmin):
    form = SystemConfigAdminForm
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
    def save_model(self, request, obj, form, change):
        if change:
            obj.atualizado_por = request.user
        super().save_model(request, obj, form, change)
