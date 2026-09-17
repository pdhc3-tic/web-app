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
from apps.sgp.serializers.production import ProductionSerializer
from apps.sgp.serializers.tecnico import TecnicoSerializer
from apps.sgp.serializers.upf import (
    HistoricoEntrySerializer,
    TitularNestedSerializer,
    UPFDetailSerializer,
    UPFListSerializer,
)
from apps.sgp.serializers.upf_documentos import (
    UPFDocumentCreateSerializer,
    UPFDocumentSerializer,
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
    "ProductionSerializer",
    "ProjetoSerializer",
    "STATUS_COR_MAP",
    "TecnicoSerializer",
    "TitularNestedSerializer",
    "UPFDetailSerializer",
    "UPFDocumentCreateSerializer",
    "UPFDocumentSerializer",
    "UPFListSerializer",
]
