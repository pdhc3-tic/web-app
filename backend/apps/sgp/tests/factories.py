import factory

from apps.core.tests.factories import MunicipalityFactory, UserFactory
from apps.sgp.models import (
    Activity,
    Comunidade,
    Cultura,
    EspecieAnimal,
    MembroFamilia,
    Production,
    Projeto,
    UPF,
    UPFDocument,
)
from apps.sgp.models.workplan import WorkPlanAcao, WorkPlanMeta


class ProjetoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Projeto

    nome = factory.Sequence(lambda n: f"Projeto {n}")
    descricao = factory.Sequence(lambda n: f"Descrição do Projeto {n}")
    ativo = True


class UPFFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = UPF

    _titular_nome = factory.Sequence(lambda n: f"Titular {n}")
    projeto = factory.SubFactory(ProjetoFactory)
    municipio = factory.SubFactory(MunicipalityFactory)
    territorio = factory.SelfAttribute("municipio.territory")
    ativa = True

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        titular_nome = kwargs.pop("_titular_nome")
        titular_cpf = kwargs.pop("cpf", kwargs.pop("titular_cpf", "86288366757"))
        titular = MembroFamilia(
            upf=None,
            parentesco="titular",
            nome_completo=titular_nome,
            cpf=titular_cpf,
            data_nasc="1990-01-01",
        )
        titular.save()
        kwargs["titular"] = titular
        upf = super()._create(model_class, *args, **kwargs)
        titular.upf = upf
        titular.save(update_fields=["upf"])
        return upf


class MembroFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MembroFamilia

    upf = factory.SubFactory("apps.sgp.tests.factories.UPFFactory")
    nome_completo = factory.Sequence(lambda n: f"Membro {n}")
    parentesco = "filho"
    data_nasc = factory.LazyFunction(
        lambda: __import__("datetime").date.today().replace(year=2000)
    )
    cpf = ""


class ComunidadeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Comunidade

    nome = factory.Sequence(lambda n: f"Comunidade {n}")
    municipio = factory.SubFactory(MunicipalityFactory)
    ativa = True
    criada_por = factory.SubFactory(UserFactory)


class UPFDocumentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = UPFDocument

    upf = factory.SubFactory(UPFFactory)
    tipo = UPFDocument.TIPO_DAP_CAF
    descricao = "Documento da UPF"
    arquivo_key = factory.LazyAttributeSequence(
        lambda obj, n: (
            f"upfs/{obj.upf.pk}/documentos/"
            f"123e4567-e89b-12d3-a456-42661417{n:04d}.pdf"
        )
    )
    nome_original = "documento.pdf"
    content_type = "application/pdf"
    tamanho_bytes = 1024
    data_documento = factory.LazyFunction(
        lambda: __import__("datetime").date(2026, 1, 15)
    )
    criado_por = factory.SubFactory(UserFactory)


class CulturaFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Cultura

    nome = factory.Sequence(lambda n: f"Cultura Produção {n}")
    categoria = Cultura.CATEGORIA_GRAOS
    ciclo = Cultura.CICLO_ANUAL
    ativa = True


class EspecieAnimalFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EspecieAnimal

    nome = factory.Sequence(lambda n: f"Espécie Produção {n}")
    categoria = EspecieAnimal.CATEGORIA_CAPRINO
    ativa = True


class ProductionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Production

    upf = factory.SubFactory(UPFFactory)
    tipo = Production.TIPO_AGRICOLA
    cultura = factory.SubFactory(CulturaFactory)
    area_ha = "1.50"
    producao_estimada = "30.00"
    unidade_producao = "saca"
    sementes_crioulas = False


# ---------------------------------------------------------------------------
# WorkPlan factories
# ---------------------------------------------------------------------------

class WorkPlanMetaFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = WorkPlanMeta
        django_get_or_create = ("numero",)

    numero = factory.Sequence(lambda n: (n % 7) + 1)
    titulo = factory.Sequence(lambda n: f"Meta {n}")
    descricao = factory.Sequence(lambda n: f"Descrição da meta {n}")
    data_inicio = factory.LazyFunction(
        lambda: __import__("datetime").date(2026, 1, 1)
    )
    data_fim = factory.LazyFunction(
        lambda: __import__("datetime").date(2026, 12, 31)
    )
    criado_por = factory.SubFactory(UserFactory)


class WorkPlanAcaoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = WorkPlanAcao

    meta = factory.SubFactory(WorkPlanMetaFactory)
    numero = factory.Sequence(lambda n: f"{(n % 7) + 1}.{(n % 5) + 1}")
    descricao = factory.Sequence(lambda n: f"Ação {n}")
    tipo_unidade = 1
    quantidade_planejada = 10
    valor_unitario = 100


# ---------------------------------------------------------------------------
# Activity factory
# ---------------------------------------------------------------------------

class ActivityFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Activity

    titulo = factory.Sequence(lambda n: f"Atividade {n}")
    tipo_atividade = "visita_tecnica"
    acao = factory.SubFactory(WorkPlanAcaoFactory)
    forma_atuacao = "realizacao"
    tecnico_responsavel = factory.SubFactory(UserFactory)
    municipio = factory.SubFactory(MunicipalityFactory)
    ambito = "municipal"
    data_inicio = factory.LazyFunction(
        lambda: __import__("datetime").date(2026, 6, 1)
    )
    data_fim = factory.LazyFunction(
        lambda: __import__("datetime").date(2026, 6, 30)
    )
    descricao_narrativa = factory.Sequence(lambda n: f"Narrativa da atividade {n}")
    status = "planejado"
    ativo = True
