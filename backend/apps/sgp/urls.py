from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ActivityViewSet,
    ComunidadeViewSet,
    CulturaListView,
    EspecieAnimalListView,
    MembroViewSet,
    ProductionViewSet,
    SGPChoicesView,
    UPFViewSet,
    UPFDocumentViewSet,
    ProjetoViewSet,
)
from .views.form_responses import FormResponseViewSet
from .views.workplan import (
    WorkPlanAcaoViewSet,
    WorkPlanDashboardView,
    WorkPlanExportView,
    WorkPlanMetaViewSet,
    WorkPlanPowerBIView,
)

router = DefaultRouter()
router.register("upfs", UPFViewSet)
router.register("projetos", ProjetoViewSet, basename="projeto")
router.register('comunidades', ComunidadeViewSet, basename='comunidade')
router.register("metas", WorkPlanMetaViewSet, basename="workplanmeta")
router.register("acoes", WorkPlanAcaoViewSet, basename="workplanacao")

sgp_router = DefaultRouter()
sgp_router.register("atividades", ActivityViewSet, basename="atividade")

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
        "sgp/upfs/<int:upf_pk>/formularios/",
        form_response_list,
        name="upf-formularios-list",
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
        "upfs/<int:upf_pk>/membros/",
        MembroViewSet.as_view(
            {"get": "list", "post": "create"}
        ),
        name="upf-membros-list",
    ),
    path(
        "upfs/<int:upf_pk>/membros/<int:pk>/",
        MembroViewSet.as_view(
            {
                "get": "retrieve",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="upf-membros-detail",
    ),
    path(
        'municipios/<int:municipio_id>/comunidades/',
        comunidade_list,
        name='comunidade-list-by-municipio',
    ),
]
