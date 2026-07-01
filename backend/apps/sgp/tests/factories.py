import factory

from apps.core.models import Municipality, State
from apps.core.tests.factories import UserFactory

from ..models import Comunidade


class StateFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = State

    sigla = factory.Iterator(['RN', 'PB', 'CE', 'PE'])
    nome = factory.Sequence(lambda n: f"Estado {n}")


class MunicipalityFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Municipality

    nome = factory.Sequence(lambda n: f"Município {n}")
    state = factory.SubFactory(StateFactory)
    codigo_ibge = factory.Sequence(lambda n: f"{n:07d}")


class ComunidadeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Comunidade

    nome = factory.Sequence(lambda n: f"Comunidade {n}")
    municipio = factory.SubFactory(MunicipalityFactory)
    ativa = True
    criada_por = factory.SubFactory(UserFactory)
