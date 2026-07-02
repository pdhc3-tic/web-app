import factory
from apps.core.tests.factories import MunicipalityFactory

from apps.sgp.models import Projeto, UPF


class ProjetoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Projeto

    nome = factory.Sequence(lambda n: f"Projeto {n}")
    descricao = factory.Sequence(lambda n: f"Descrição do Projeto {n}")
    ativo = True


class UPFFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = UPF

    projeto = factory.SubFactory(ProjetoFactory)
    nome_titular = factory.Sequence(lambda n: f"Titular {n}")
    cpf = "86288366757"
    municipio = factory.SubFactory(MunicipalityFactory)
    territorio = factory.SelfAttribute("municipio.territory")
    ativa = True
