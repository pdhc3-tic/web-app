from django.contrib import admin

from apps.sgd.models import ApprovalStep, Demand, DemandDocument, DemandIndividualLimit, DemandRequest


@admin.register(Demand)
class DemandAdmin(admin.ModelAdmin):
    list_display = ["titulo", "activity", "status", "solicitante", "criado_em"]
    list_filter = ["status"]
    search_fields = ["titulo", "solicitante__nome", "activity__titulo"]


@admin.register(DemandRequest)
class DemandRequestAdmin(admin.ModelAdmin):
    list_display = ["demanda", "tipo", "rubrica", "valor_estimado", "valor_autorizado", "valor_pago"]
    list_filter = ["tipo", "rubrica"]


@admin.register(DemandDocument)
class DemandDocumentAdmin(admin.ModelAdmin):
    list_display = ["demanda", "tipo", "nome_original", "ativo", "enviado_em"]
    list_filter = ["tipo", "ativo"]


@admin.register(ApprovalStep)
class ApprovalStepAdmin(admin.ModelAdmin):
    list_display = ["demanda", "etapa", "acao", "responsavel", "criado_em"]
    list_filter = ["etapa", "acao"]


@admin.register(DemandIndividualLimit)
class DemandIndividualLimitAdmin(admin.ModelAdmin):
    list_display = ["solicitante", "rubrica", "valor_limite", "valor_comprometido", "valor_executado"]
    list_filter = ["rubrica"]
    search_fields = ["solicitante__nome"]
