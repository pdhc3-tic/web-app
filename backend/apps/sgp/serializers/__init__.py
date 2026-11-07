"""Reexporta a API pública de `apps.sgp.serializers` — a lógica de cada
serializer está nos submódulos, um por entidade."""

from apps.sgp.serializers.activity import ActivityDetailSerializer, ActivityListSerializer
from apps.sgp.serializers.activity_calendario import (
    STATUS_COR_MAP,
    ActivityCalendarioSerializer,
)
from apps.sgp.serializers.activity_documentos import ActivityDocumentSerializer
from apps.sgp.serializers.activity_foto import ActivityPhotoSerializer
from apps.sgp.serializers.catalogos import (
    CatalogoProductionNestedSerializer,
    CulturaSerializer,
    EspecieAnimalSerializer,
    ProjetoSerializer,
)
from apps.sgp.serializers.comunidade import ComunidadeSerializer
from apps.sgp.serializers.common import (
    EstadoNestedSerializer,
    MunicipioNestedSerializer,
    NestedSerializer,
)
from apps.sgp.serializers.form_responses import (
    AvailableFormSerializer,
    FormResponseDetailSerializer,
    FormResponseFormularioOptionSerializer,
    FormResponseListSerializer,
    FormResponseReceiveSerializer,
)
from apps.sgp.serializers.membro import (
    MembroDetailSerializer,
    MembroExportQuerySerializer,
    MembroListSerializer,
)
from apps.sgp.serializers.production import (
    ProducaoConsolidadaSerializer,
    ProductionSerializer,
)
from apps.sgp.serializers.tecnico import TecnicoSerializer
from apps.sgp.serializers.ufpa import (
    HistoricoEntrySerializer,
    TitularNestedSerializer,
    UFPADetailSerializer,
    UFPAListSerializer,
)
from apps.sgp.serializers.ufpa_documentos import (
    UFPADocumentCreateSerializer,
    UFPADocumentSerializer,
)

__all__ = [
    "ActivityCalendarioSerializer",
    "ActivityDetailSerializer",
    "ActivityDocumentSerializer",
    "ActivityListSerializer",
    "ActivityPhotoSerializer",
    "AvailableFormSerializer",
    "CatalogoProductionNestedSerializer",
    "ComunidadeSerializer",
    "CulturaSerializer",
    "EspecieAnimalSerializer",
    "EstadoNestedSerializer",
    "FormResponseDetailSerializer",
    "FormResponseFormularioOptionSerializer",
    "FormResponseListSerializer",
    "FormResponseReceiveSerializer",
    "HistoricoEntrySerializer",
    "MembroDetailSerializer",
    "MembroExportQuerySerializer",
    "MembroListSerializer",
    "MunicipioNestedSerializer",
    "NestedSerializer",
    "ProducaoConsolidadaSerializer",
    "ProductionSerializer",
    "ProjetoSerializer",
    "STATUS_COR_MAP",
    "TecnicoSerializer",
    "TitularNestedSerializer",
    "UFPADetailSerializer",
    "UFPADocumentCreateSerializer",
    "UFPADocumentSerializer",
    "UFPAListSerializer",
]
