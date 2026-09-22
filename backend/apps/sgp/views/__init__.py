"""Reexporta a API pública de `apps.sgp.views` — a lógica de cada view está
nos submódulos, um por entidade."""

from apps.sgp.views.activity import ActivityViewSet
from apps.sgp.views.activity_documentos import ActivityDocumentMixin
from apps.sgp.views.activity_foto import ActivityPhotoMixin
from apps.sgp.views.catalogos import CatalogoListView, CulturaListView, EspecieAnimalListView
from apps.sgp.views.choices import SGPChoicesView
from apps.sgp.views.comunidade import ComunidadePagination, ComunidadeViewSet, QSearchFilter
from apps.sgp.views.membro import (
    MembroExportView,
    MembroViewSet,
    _membros_csv_response,
    data_limite_aniversario,
)
from apps.sgp.tasks import sync_activity_to_google_calendar
from apps.sgp.views.production import ProductionViewSet
from apps.sgp.views.projeto import ProjetoViewSet
from apps.sgp.views.tecnico import TecnicoViewSet, tecnicos_acessiveis_ao_usuario
from apps.sgp.views.upf import (
    UPF_ACCESS_ROLES,
    UPFViewSet,
    upfs_acessiveis_ao_usuario,
)
from apps.sgp.views.upf_documentos import UPFDocumentViewSet
from apps.sgp.views.upf_foto import UPFPhotoMixin

__all__ = [
    "ActivityDocumentMixin",
    "ActivityPhotoMixin",
    "ActivityViewSet",
    "CatalogoListView",
    "ComunidadePagination",
    "ComunidadeViewSet",
    "CulturaListView",
    "EspecieAnimalListView",
    "MembroExportView",
    "MembroViewSet",
    "ProductionViewSet",
    "ProjetoViewSet",
    "QSearchFilter",
    "SGPChoicesView",
    "TecnicoViewSet",
    "UPFDocumentViewSet",
    "UPFPhotoMixin",
    "UPFViewSet",
    "UPF_ACCESS_ROLES",
    "_membros_csv_response",
    "data_limite_aniversario",
    "sync_activity_to_google_calendar",
    "tecnicos_acessiveis_ao_usuario",
    "upfs_acessiveis_ao_usuario",
]
