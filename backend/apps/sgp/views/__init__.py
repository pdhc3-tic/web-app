"""Reexporta a API pública de `apps.sgp.views` — a lógica de cada view está
nos submódulos, um por entidade."""

from apps.sgp.views.activity import ActivityViewSet
from apps.sgp.views.activity_documentos import ActivityDocumentMixin
from apps.sgp.views.activity_foto import ActivityPhotoMixin
from apps.sgp.views.catalogos import CatalogoListView, CulturaListView, EspecieAnimalListView
from apps.sgp.views.choices import SGPChoicesView
from apps.sgp.views.comunidade import ComunidadePagination, ComunidadeViewSet, QSearchFilter
from apps.sgp.views.exportacao import ExportacaoViewSet
from apps.sgp.views.membro import (
    MembroExportView,
    MembroViewSet,
    _membros_csv_response,
    data_limite_aniversario,
)
from apps.sgp.tasks import sync_google_calendar_event
from apps.sgp.views.production import ProducaoConsolidadaViewSet, ProductionViewSet
from apps.sgp.views.projeto import ProjetoViewSet
from apps.sgp.views.tecnico import TecnicoViewSet
from apps.sgp.views.ufpa import UFPA_ACCESS_ROLES, UFPAViewSet
from apps.sgp.views.ufpa_documentos import UFPADocumentViewSet
from apps.sgp.views.ufpa_foto import UFPAPhotoMixin

__all__ = [
    "ActivityDocumentMixin",
    "ActivityPhotoMixin",
    "ActivityViewSet",
    "CatalogoListView",
    "ComunidadePagination",
    "ComunidadeViewSet",
    "CulturaListView",
    "EspecieAnimalListView",
    "ExportacaoViewSet",
    "MembroExportView",
    "MembroViewSet",
    "ProducaoConsolidadaViewSet",
    "ProductionViewSet",
    "ProjetoViewSet",
    "QSearchFilter",
    "SGPChoicesView",
    "TecnicoViewSet",
    "UFPADocumentViewSet",
    "UFPAPhotoMixin",
    "UFPAViewSet",
    "UFPA_ACCESS_ROLES",
    "_membros_csv_response",
    "data_limite_aniversario",
    "sync_google_calendar_event",
]
