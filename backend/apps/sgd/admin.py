from decimal import Decimal

from django import forms
from django.contrib import admin
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.sgd.models import (
    ApprovalStep,
    ArloFieldMapping,
    ArloImport,
    Demand,
    DemandDocument,
    DemandRequest,
    TipoSolicitacao,
)
from apps.sgd.services import orcamento as orcamento_service
from apps.sgp.models import SpendingLimit

ZERO = Decimal("0")


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
    list_select_related = ["demanda", "tipo", "rubrica"]
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


class SpendingLimitAdminForm(forms.ModelForm):
    class Meta:
        model = SpendingLimit
        fields = "__all__"

    def clean(self):
        dados = super().clean()
        novo = self.instance.pk is None
        # Na edição, estes campos são somente leitura e não vêm no formulário.
        escopo = dados.get("escopo") or self.instance.escopo
        if escopo == SpendingLimit.Escopo.PERFIL:
            self.add_error("escopo", "O padrão por perfil é cadastrado em /sgp/orcamento/limites/.")
            return dados
        if novo and not dados.get("user"):
            self.add_error("user", "Obrigatório no limite individual.")
        mudou_o_valor = "valor_limite" in self.changed_data
        if (not self.instance.herdado or mudou_o_valor) and not (dados.get("justificativa") or "").strip():
            self.add_error("justificativa", "Obrigatória em limite individual e em alteração de valor.")
        if not self.errors:
            self._conferir_saldo_e_periodo(dados)
        return dados

    def _conferir_saldo_e_periodo(self, dados) -> None:
        novo = self.instance.pk is None
        user = dados["user"].pk if novo else self.instance.user_id
        rubrica = dados["rubrica"].pk if novo else self.instance.rubrica_id
        territorio_id = orcamento_service.territorio_do_pool(user)
        inicio = dados["periodo_inicio"] if novo else self.instance.periodo_inicio
        if novo:
            efetivo = orcamento_service.limite_efetivo(solicitante_id=user, rubrica_id=rubrica, data=inicio)
            valor_atual = efetivo.valor_limite if efetivo else ZERO
        else:
            valor_atual = self.instance.valor_limite
        aumento = dados["valor_limite"] - valor_atual
        try:
            if novo:
                orcamento_service.exigir_sem_sobreposicao(user, rubrica, inicio, dados["periodo_fim"])
            if territorio_id and aumento > ZERO:
                orcamento_service.exigir_dentro_do_pool(rubrica, [territorio_id], inicio, ajuste=aumento)
        except DRFValidationError as exc:
            campo, mensagem = next(iter(exc.detail.items()))
            self.add_error("valor_limite" if campo == "valor_limite" else None, str(mensagem[0] if isinstance(mensagem, list) else mensagem))

    def clean_valor_limite(self):
        valor = self.cleaned_data["valor_limite"]
        if valor < 0:
            raise forms.ValidationError("Não pode ser negativo.")
        return valor


@admin.register(SpendingLimit)
class SpendingLimitAdmin(SalvaSoOQueOFormularioAlterou, admin.ModelAdmin):
    form = SpendingLimitAdminForm
    list_display = [
        "escopo", "user", "perfil", "rubrica", "periodo_inicio", "periodo_fim",
        "valor_limite", "valor_comprometido", "valor_executado",
    ]
    list_filter = ["escopo", "rubrica"]
    search_fields = ["user__nome"]
    readonly_fields = ["valor_comprometido", "valor_executado", "criado_por", "herdado", "territorio"]

    def get_readonly_fields(self, request, obj=None):
        # O comprometido é a soma das reservas desse solicitante nessa rubrica:
        # mover o limite para outro par deixaria as reservas sem limite.
        if obj is None:
            return self.readonly_fields
        return [*self.readonly_fields, "escopo", "user", "perfil", "rubrica", "periodo_inicio", "periodo_fim"]

    def get_object(self, request, object_id, from_field=None):
        # O Admin roda o POST da edição e da exclusão numa transação: travado
        # aqui, o limite conferido é o mesmo que será salvo ou excluído.
        obj = super().get_object(request, object_id, from_field)
        if obj is None or request.method != "POST":
            return obj
        return SpendingLimit.objects.select_for_update(of=("self",)).get(pk=obj.pk)

    def save_model(self, request, obj, form, change):
        valor_anterior = form.initial.get("valor_limite")
        if not change:
            obj.criado_por = request.user
            obj.territorio_id = orcamento_service.territorio_do_usuario(obj.user_id)
        elif obj.herdado and obj.valor_limite != valor_anterior:
            # O valor deixou de ser o do padrão do perfil: como na rota, vira sobrescrita.
            obj.herdado = False
            form.changed_data.append("herdado")
        super().save_model(request, obj, form, change)
        tipo = orcamento_service.TipoTransacao.AUMENTO_LIMITE
        if not change:
            orcamento_service.auditar_criacao_do_limite(obj, request.user)
            if obj.escopo == SpendingLimit.Escopo.INDIVIDUAL:
                orcamento_service.registrar_alteracao_do_limite(
                    limite=obj, tipo=tipo, valor=obj.valor_limite, usuario=request.user,
                    justificativa=obj.justificativa,
                )
        elif obj.valor_limite != valor_anterior:
            orcamento_service.auditar_alteracao_do_limite(obj, valor_anterior=valor_anterior, usuario=request.user)
            if obj.escopo == SpendingLimit.Escopo.INDIVIDUAL:
                orcamento_service.registrar_alteracao_do_limite(
                    limite=obj, tipo=tipo, valor=obj.valor_limite - valor_anterior,
                    usuario=request.user, justificativa=obj.justificativa,
                )

    def has_change_permission(self, request, obj=None):
        # O padrão por perfil tem regra própria de vigência: só pela rota de limites.
        if obj is not None and obj.escopo == SpendingLimit.Escopo.PERFIL:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        # Com saldo, as reservas e execuções ficariam sem limite. O `obj` do POST
        # da exclusão vem travado por `get_object`.
        if obj is not None and (obj.valor_comprometido or obj.valor_executado):
            return False
        # Sem o padrão, o perfil inteiro fica sem limite: só pela rota de limites.
        if obj is not None and obj.escopo == SpendingLimit.Escopo.PERFIL:
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


@admin.register(TipoSolicitacao)
class TipoSolicitacaoAdmin(admin.ModelAdmin):
    list_display = ["nome", "slug", "rubrica", "validador", "ativo", "ordem", "atualizado_em"]
    list_filter = ["ativo", "rubrica"]
    list_select_related = ["rubrica"]

    # O catálogo é alterado pela API, que valida o schema e audita a operação.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
