from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ActivityViewSet,
    ComunidadeViewSet,
    CulturaListView,
    EspecieAnimalListView,
    MembroExportView,
    MembroViewSet,
    ProductionViewSet,
    SGPChoicesView,
    TecnicoViewSet,
    UPFViewSet,
    UPFDocumentViewSet,
    ProjetoViewSet,
)
from .views.form_responses import (
    AvailableFormListView,
    FormResponseFormularioOptionsView,
    FormResponseReceiveView,
    FormResponseViewSet,
)
from .views.workplan import (
    WorkPlanAcaoViewSet,
    WorkPlanDashboardView,
    WorkPlanExportView,
    WorkPlanMetaViewSet,
    WorkPlanPowerBIView,
)
from .views.budget import (
    BudgetAllocationViewSet,
    BudgetPainelView,
    RemanejamentoView,
    SaldoConsultaView,
)

router = DefaultRouter()
router.register("upfs", UPFViewSet)
router.register("projetos", ProjetoViewSet, basename="projeto")
router.register('comunidades', ComunidadeViewSet, basename='comunidade')
router.register("metas", WorkPlanMetaViewSet, basename="workplanmeta")
router.register("acoes", WorkPlanAcaoViewSet, basename="workplanacao")

sgp_router = DefaultRouter()
sgp_router.register("atividades", ActivityViewSet, basename="atividade")
sgp_router.register("tecnicos", TecnicoViewSet, basename="tecnico")

comunidade_list = ComunidadeViewSet.as_view({
    'get': 'list',
    'post': 'create',
})
upf_document_list = UPFDocumentViewSet.as_view({
    "get": "list",
    "post": "create",
})
upf_document_upload_url = UPFDocumentViewSet.as_view({
    "post": "upload_url",
})
upf_document_detail = UPFDocumentViewSet.as_view({
    "delete": "destroy",
})
upf_document_download = UPFDocumentViewSet.as_view({
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

urlpatterns = router.urls + [
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
        "sgp/plano-trabalho/powerbi/",
        WorkPlanPowerBIView.as_view(),
        name="workplan-power-bi",
    ),
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
        "sgp/upfs/<int:upf_pk>/formularios/",
        form_response_list,
        name="upf-formularios-list",
    ),
    path(
        "sgp/upfs/<int:upf_pk>/formularios/exportar/",
        form_response_export,
        name="upf-formularios-export",
    ),
    path(
        "sgp/upfs/<int:upf_pk>/formularios/opcoes/",
        FormResponseFormularioOptionsView.as_view(),
        name="upf-formularios-opcoes",
    ),
    path(
        "sgp/upfs/<int:upf_pk>/formularios/<int:pk>/",
        form_response_detail,
        name="upf-formularios-detail",
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
        "upfs/<int:upf_pk>/documentos/",
        upf_document_list,
        name="upf-documentos-list",
    ),
    path(
        "upfs/<int:upf_pk>/documentos/upload-url/",
        upf_document_upload_url,
        name="upf-documentos-upload-url",
    ),
    path(
        "upfs/<int:upf_pk>/documentos/<int:pk>/download/",
        upf_document_download,
        name="upf-documentos-download",
    ),
    path(
        "upfs/<int:upf_pk>/documentos/<int:pk>/",
        upf_document_detail,
        name="upf-documentos-detail",
    ),
    path(
        "upfs/<int:upf_pk>/producao/",
        production_list,
        name="upf-producao-list",
    ),
    path(
        "upfs/<int:upf_pk>/producao/<int:pk>/",
        production_detail,
        name="upf-producao-detail",
    ),
    path(
        "sgp/upfs/<int:upf_pk>/membros/",
        MembroViewSet.as_view(
            {"get": "list", "post": "create"}
        ),
        name="upf-membros-list",
    ),
    path(
        "sgp/upfs/<int:upf_pk>/membros/<int:pk>/",
        MembroViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="upf-membros-detail",
    ),
    path(
        "sgp/upfs/<int:upf_pk>/membros/resumo/",
        MembroViewSet.as_view({"get": "resumo"}),
        name="upf-membros-resumo",
    ),
    path(
        "sgp/upfs/<int:upf_pk>/membros/transferir-titularidade/",
        MembroViewSet.as_view({"post": "transferir_titularidade"}),
        name="upf-membros-transferir-titularidade",
    ),
    path(
        "sgp/upfs/<int:upf_pk>/membros/exportar/",
        MembroViewSet.as_view({"get": "exportar"}),
        name="upf-membros-exportar",
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
        WorkPlanMetaViewSet.as_view({"get": "orcamento"}),
        name="workplanmeta-orcamento",
    ),
    path(
        "sgp/metas/<int:meta_pk>/orcamento/alocacoes/",
        BudgetAllocationViewSet.as_view({"post": "create"}),
        name="budget-alocacoes-create",
    ),
    path(
        "sgp/orcamento/alocacoes/<int:pk>/",
        BudgetAllocationViewSet.as_view({"patch": "partial_update", "delete": "destroy"}),
        name="budget-alocacoes-detail",
    ),
    path(
        "sgp/orcamento/alocacoes/<int:pk>/transacoes/",
        BudgetAllocationViewSet.as_view({"get": "transacoes"}),
        name="budget-alocacoes-transacoes",
    ),
    path(
        "sgp/orcamento/saldo/",
        SaldoConsultaView.as_view(),
        name="budget-saldo",
    ),
    path(
        "sgp/orcamento/remanejamentos/",
        RemanejamentoView.as_view(),
        name="budget-remanejamentos",
    ),
    path(
        "sgp/orcamento/painel/",
        BudgetPainelView.as_view(),
        name="budget-painel",
    ),
]
