from rest_framework.viewsets import ModelViewSet

from .models import Comunidade, Estado, Municipio, Territorio
from .serializers import (
    ComunidadeSerializer,
    EstadoSerializer,
    MunicipioSerializer,
    TerritorioSerializer,
)


class EstadoViewSet(ModelViewSet):
    queryset = Estado.objects.all()
    serializer_class = EstadoSerializer


class TerritorioViewSet(ModelViewSet):
    queryset = Territorio.objects.all()
    serializer_class = TerritorioSerializer


class MunicipioViewSet(ModelViewSet):
    queryset = Municipio.objects.select_related("estado", "territorio").all()
    serializer_class = MunicipioSerializer


class ComunidadeViewSet(ModelViewSet):
    queryset = Comunidade.objects.select_related("municipio", "territorio").all()
    serializer_class = ComunidadeSerializer
