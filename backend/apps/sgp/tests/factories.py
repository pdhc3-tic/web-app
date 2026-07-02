import factory
from apps.core.tests.factories import MunicipalityFactory

from apps.sgp.models import MembroFamilia, Projeto, UPF


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


class MembroFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MembroFamilia

    upf = factory.SubFactory(UPFFactory)
    nome_completo = factory.Sequence(lambda n: f"Membro {n}")
    parentesco = "filho"
    data_nasc = factory.LazyFunction(
        lambda: __import__("datetime").date.today().replace(year=2000)
    )
    cpf = ""
