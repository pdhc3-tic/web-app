from django import forms
from django.contrib import admin

from apps.sgd.models import (
    ApprovalStep,
    ArloFieldMapping,
    ArloImport,
    Demand,
    DemandDocument,
    DemandIndividualLimit,
    DemandRequest,
    DemandTypeRubricaMapping,
)
from apps.sgd.services import auditoria as auditoria_service


class SalvaSoOQueOFormularioAlterou:
    """`readonly_fields` só tira o campo do formulário: o salvamento padrão do
    Admin regrava a instância inteira como foi carregada e desfaria o saldo que
    outra operação gravou depois disso."""

    def save_model(self, request, obj, form, change):
        if change:
            obj.save(update_fields=[*form.changed_data, "atualizado_em"])
        else:
            super().save_model(request, obj, form, change)


@admin.register(Demand)
class DemandAdmin(admin.ModelAdmin):
    list_display = ["titulo", "activity", "status", "solicitante", "criado_em"]
    list_filter = ["status"]
    search_fields = ["titulo", "solicitante__nome", "activity__titulo"]

    # Status, solicitante e atividade decidem onde está o saldo reservado, e a
    # API não exclui demanda, só cancela: aqui é só consulta.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DemandRequest)
class DemandRequestAdmin(SalvaSoOQueOFormularioAlterou, admin.ModelAdmin):
    list_display = ["demanda", "tipo", "rubrica", "valor_estimado", "valor_autorizado", "valor_pago"]
    list_filter = ["tipo", "rubrica"]

    # Cada campo move saldo (valores, demanda, rubrica), é derivado de outro
    # (rubrica do tipo, valor de `campos_json`) ou é o CPF, que a validação do
    # serviço tira de `campos_json`: só os serviços da demanda alteram.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DemandDocument)
class DemandDocumentAdmin(admin.ModelAdmin):
    list_display = ["demanda", "tipo", "nome_original", "ativo", "enviado_em"]
    list_filter = ["tipo", "ativo"]


@admin.register(ApprovalStep)
class ApprovalStepAdmin(admin.ModelAdmin):
    list_display = ["demanda", "etapa", "acao", "responsavel", "criado_em"]
    list_filter = ["etapa", "acao"]


class DemandIndividualLimitAdminForm(forms.ModelForm):
    class Meta:
        model = DemandIndividualLimit
        fields = "__all__"

    def clean_valor_limite(self):
        valor = self.cleaned_data["valor_limite"]
        if valor < 0:
            raise forms.ValidationError("Não pode ser negativo.")
        erro = self.instance.pk and self.instance.erro_de_reducao(valor)
        if erro:
            raise forms.ValidationError(erro)
        return valor


@admin.register(DemandIndividualLimit)
class DemandIndividualLimitAdmin(SalvaSoOQueOFormularioAlterou, admin.ModelAdmin):
    form = DemandIndividualLimitAdminForm
    list_display = ["solicitante", "rubrica", "valor_limite", "valor_comprometido", "valor_executado"]
    list_filter = ["rubrica"]
    search_fields = ["solicitante__nome"]
    readonly_fields = ["valor_comprometido", "valor_executado", "criado_por"]

    def get_readonly_fields(self, request, obj=None):
        # O comprometido é a soma das reservas desse solicitante nessa rubrica:
        # mover o limite para outro par deixaria as reservas sem limite.
        if obj is None:
            return self.readonly_fields
        return [*self.readonly_fields, "solicitante", "rubrica"]

    def get_object(self, request, object_id, from_field=None):
        # O Admin roda o POST da edição e da exclusão numa transação: travado
        # aqui, o limite conferido é o mesmo que será salvo ou excluído.
        obj = super().get_object(request, object_id, from_field)
        if obj is None or request.method != "POST":
            return obj
        return DemandIndividualLimit.objects.select_for_update().get(pk=obj.pk)

    def save_model(self, request, obj, form, change):
        valor_anterior = form.initial.get("valor_limite")
        if not change:
            obj.criado_por = request.user
        super().save_model(request, obj, form, change)
        if not change:
            auditoria_service.registrar_limite_criado(obj, usuario=request.user)
        elif obj.valor_limite != valor_anterior:
            auditoria_service.registrar_limite_alterado(obj, valor_anterior=valor_anterior, usuario=request.user)

    def has_delete_permission(self, request, obj=None):
        # Com saldo, as reservas e execuções ficariam sem limite. O `obj` do POST
        # da exclusão vem travado por `get_object`.
        if obj is not None and (obj.valor_comprometido or obj.valor_executado):
            return False
        return super().has_delete_permission(request, obj)

    def get_actions(self, request):
        # A exclusão em lote não consulta `has_delete_permission` de cada limite.
        acoes = super().get_actions(request)
        acoes.pop("delete_selected", None)
        return acoes


@admin.register(ArloFieldMapping)
class ArloFieldMappingAdmin(admin.ModelAdmin):
    list_display = ["direcao", "ordem", "campo_sgd", "coluna_arlo", "formato", "ativo"]
    list_filter = ["direcao", "ativo"]


@admin.register(ArloImport)
class ArloImportAdmin(admin.ModelAdmin):
    list_display = ["tipo", "status", "operado_por", "operado_em", "total_registros", "registros_ok"]
    list_filter = ["tipo", "status"]


@admin.register(DemandTypeRubricaMapping)
class DemandTypeRubricaMappingAdmin(admin.ModelAdmin):
    list_display = ["tipo", "rubrica", "ativo", "atualizado_em"]
    list_filter = ["tipo", "ativo"]
