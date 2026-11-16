from django.urls import include, path
from rest_framework.routers import DefaultRouter, SimpleRouter

from .views import (
    ActivityViewSet,
    ComunidadeViewSet,
    CulturaListView,
    EspecieAnimalListView,
    ExportacaoViewSet,
    MembroExportView,
    MembroViewSet,
    ProducaoConsolidadaViewSet,
    ProductionViewSet,
    SGPChoicesView,
    TecnicoViewSet,
    UFPAViewSet,
    UFPADocumentViewSet,
    ProjetoViewSet,
)
from .views.form_responses import (
    AvailableFormListView,
    FormResponseFormularioOptionsView,
    FormResponseReceiveView,
    FormResponseViewSet,
)
from .views.glosa_risk import GlosaRiskListView
from .views.workplan import (
    IndicatorViewSet,
    WorkPlanAcaoViewSet,
    WorkPlanDashboardView,
    WorkPlanExportView,
    WorkPlanMetaViewSet,
    WorkPlanPowerBIView,
    WorkPlanSubmetaViewSet,
    WorkPlanVisaoIndicadorView,
)

router = DefaultRouter()
router.register("projetos", ProjetoViewSet, basename="projeto")
router.register('comunidades', ComunidadeViewSet, basename='comunidade')
router.register("metas", WorkPlanMetaViewSet, basename="workplanmeta")
router.register("acoes", WorkPlanAcaoViewSet, basename="workplanacao")

sgp_router = DefaultRouter()
sgp_router.register("atividades", ActivityViewSet, basename="atividade")
sgp_router.register("tecnicos", TecnicoViewSet, basename="tecnico")
sgp_router.register("producao", ProducaoConsolidadaViewSet, basename="producao-consolidada")
sgp_router.register("exportacoes", ExportacaoViewSet, basename="exportacao")
sgp_router.register("submetas", WorkPlanSubmetaViewSet, basename="workplansubmeta")
sgp_router.register("indicadores", IndicatorViewSet, basename="indicator")

ufpa_router = SimpleRouter()
ufpa_router.register("", UFPAViewSet, basename="ufpa")

comunidade_list = ComunidadeViewSet.as_view({
    'get': 'list',
    'post': 'create',
})
ufpa_document_list = UFPADocumentViewSet.as_view({
    "get": "list",
    "post": "create",
})
ufpa_document_upload_url = UFPADocumentViewSet.as_view({
    "post": "upload_url",
})
ufpa_document_detail = UFPADocumentViewSet.as_view({
    "delete": "destroy",
})
ufpa_document_download = UFPADocumentViewSet.as_view({
    "get": "download",
})
production_list = ProductionViewSet.as_view({
    "get": "list",
    "post": "create",
})
production_detail = ProductionViewSet.as_view({
    "get": "retrieve",
    "patch": "partial_update",
    "delete": "destroy",
})
form_response_list = FormResponseViewSet.as_view({"get": "list"})
form_response_detail = FormResponseViewSet.as_view({"get": "retrieve"})
form_response_export = FormResponseViewSet.as_view({"get": "export"})

rotas_da_ufpa = [
    path(
        "<int:ufpa_pk>/formularios/",
        form_response_list,
        name="ufpa-formularios-list",
    ),
    path(
        "<int:ufpa_pk>/formularios/exportar/",
        form_response_export,
        name="ufpa-formularios-export",
    ),
    path(
        "<int:ufpa_pk>/formularios/opcoes/",
        FormResponseFormularioOptionsView.as_view(),
        name="ufpa-formularios-opcoes",
    ),
    path(
        "<int:ufpa_pk>/formularios/<int:pk>/",
        form_response_detail,
        name="ufpa-formularios-detail",
    ),
    path(
        "<int:ufpa_pk>/documentos/",
        ufpa_document_list,
        name="ufpa-documentos-list",
    ),
    path(
        "<int:ufpa_pk>/documentos/upload-url/",
        ufpa_document_upload_url,
        name="ufpa-documentos-upload-url",
    ),
    path(
        "<int:ufpa_pk>/documentos/<int:pk>/download/",
        ufpa_document_download,
        name="ufpa-documentos-download",
    ),
    path(
        "<int:ufpa_pk>/documentos/<int:pk>/",
        ufpa_document_detail,
        name="ufpa-documentos-detail",
    ),
    path(
        "<int:ufpa_pk>/producao/",
        production_list,
        name="ufpa-producao-list",
    ),
    path(
        "<int:ufpa_pk>/producao/<int:pk>/",
        production_detail,
        name="ufpa-producao-detail",
    ),
    path(
        "<int:ufpa_pk>/membros/",
        MembroViewSet.as_view(
            {"get": "list", "post": "create"}
        ),
        name="ufpa-membros-list",
    ),
    path(
        "<int:ufpa_pk>/membros/<int:pk>/",
        MembroViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="ufpa-membros-detail",
    ),
    path(
        "<int:ufpa_pk>/membros/resumo/",
        MembroViewSet.as_view({"get": "resumo"}),
        name="ufpa-membros-resumo",
    ),
    path(
        "<int:ufpa_pk>/membros/transferir-titularidade/",
        MembroViewSet.as_view({"post": "transferir_titularidade"}),
        name="ufpa-membros-transferir-titularidade",
    ),
    path(
        "<int:ufpa_pk>/membros/exportar/",
        MembroViewSet.as_view({"get": "exportar"}),
        name="ufpa-membros-exportar",
    ),
    *ufpa_router.urls,
]

urlpatterns = router.urls + [
    path("sgp/ufpas/", include(rotas_da_ufpa)),
    # Rotas antigas, por um ciclo. Com namespace, `reverse` só resolve a rota canônica.
    path("sgp/upfs/", include((rotas_da_ufpa, "sgp"), namespace="alias_sgp_upfs")),
    path("upfs/", include((rotas_da_ufpa, "sgp"), namespace="alias_upfs")),
    # Painel consolidado do Plano de Trabalho (Issue #136).
    path(
        "sgp/plano-trabalho/painel/",
        WorkPlanDashboardView.as_view(),
        name="workplan-dashboard",
    ),
    path(
        "sgp/plano-trabalho/exportar/",
        WorkPlanExportView.as_view(),
        name="workplan-export",
    ),
    path(
        "sgp/plano-trabalho/indicadores/",
        WorkPlanVisaoIndicadorView.as_view(),
        name="workplan-visao-indicador",
    ),
    path(
        "sgp/plano-trabalho/powerbi/",
        WorkPlanPowerBIView.as_view(),
        name="workplan-power-bi",
    ),
    path("sgp/glosa-riscos/", GlosaRiskListView.as_view(), name="glosa-risco-list"),
    path("sgp/", include(sgp_router.urls)),
    path(
        "sgp/formularios-disponiveis/",
        AvailableFormListView.as_view(),
        name="formularios-disponiveis-list",
    ),
    path(
        "sgp/formularios/respostas/",
        FormResponseReceiveView.as_view(),
        name="formulario-resposta-receive",
    ),
    path(
        "choices/",
        SGPChoicesView.as_view(),
        name="sgp-choices",
    ),
    path(
        "catalogos/culturas/",
        CulturaListView.as_view(),
        name="catalogo-culturas-list",
    ),
    path(
        "catalogos/especies-animais/",
        EspecieAnimalListView.as_view(),
        name="catalogo-especies-animais-list",
    ),
    path(
        "sgp/membros/exportar/",
        MembroExportView.as_view(),
        name="membros-exportar",
    ),
    path(
        'municipios/<int:municipio_id>/comunidades/',
        comunidade_list,
        name='comunidade-list-by-municipio',
    ),
    path(
        "sgp/metas/<int:pk>/orcamento/",
        WorkPlanMetaViewSet.as_view({"get": "orcamento"}, pagination_class=None),
        name="workplanmeta-orcamento",
    ),
    path("", include("apps.sgp.budget.urls")),
]
