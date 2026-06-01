from django_filters import rest_framework as django_filters
from rest_framework import filters, viewsets
from rest_framework.permissions import IsAuthenticated

from apps.core.models import Municipality, Role, State, Territory
from apps.core.serializers import MunicipalitySerializer, RoleSerializer, StateSerializer, TerritorySerializer


class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, django_filters.DjangoFilterBackend]
    search_fields = ['nome', 'slug']
    filterset_fields = ['ativo']


class StateViewSet(viewsets.ModelViewSet):
    queryset = State.objects.all()
    serializer_class = StateSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['nome', 'sigla']


class TerritoryViewSet(viewsets.ModelViewSet):
    queryset = Territory.objects.all()
    serializer_class = TerritorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, django_filters.DjangoFilterBackend]
    search_fields = ['nome']
    filterset_fields = ['ativo', 'articulador']


class MunicipalityViewSet(viewsets.ModelViewSet):
    queryset = Municipality.objects.all()
    serializer_class = MunicipalitySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, django_filters.DjangoFilterBackend]
    search_fields = ['nome', 'codigo_ibge']
    filterset_fields = ['state', 'territory']
