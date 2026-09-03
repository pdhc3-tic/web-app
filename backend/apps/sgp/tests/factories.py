import factory
from django.utils import timezone

from apps.core.tests.factories import MunicipalityFactory, TerritoryFactory, UserFactory
from apps.sgp.models import (
    Activity,
    BudgetAllocation,
    BudgetRubrica,
    BudgetTransaction,
    Comunidade,
    Cultura,
    EspecieAnimal,
    FormResponse,
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
    _titular_cpf = factory.Sequence(lambda n: f"{n:011d}")
    projeto = factory.SubFactory(ProjetoFactory)
    municipio = factory.SubFactory(MunicipalityFactory)
    territorio = factory.SelfAttribute("municipio.territory")
    ativa = True

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        titular_nome = kwargs.pop("_titular_nome")
        titular_cpf = kwargs.pop("cpf", kwargs.pop("titular_cpf", kwargs.pop("_titular_cpf")))
        titular = MembroFamilia(
            upf=None,
            grau_parentesco="titular",
            nome_completo=titular_nome,
            cpf=titular_cpf,
            data_nascimento="1990-01-01",
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
    grau_parentesco = "filho"
    data_nascimento = factory.LazyFunction(
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


class FormResponseFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = FormResponse

    upf = factory.SubFactory(UPFFactory)
    formulario_id = factory.Sequence(lambda n: n + 1)
    formulario_nome = factory.Sequence(lambda n: f"Formulário {n}")
    formulario_versao = "1.0"
    data_preenchimento = factory.LazyFunction(timezone.now)
    respondente = "Técnico de Campo"
    status = FormResponse.Status.SUBMETIDO
    respostas_json = factory.LazyFunction(lambda: {"pergunta_1": "resposta"})
    origem = FormResponse.Origem.WEB


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
        lambda: timezone.make_aware(__import__("datetime").datetime(2026, 6, 1, 8, 0))
    )
    data_fim = factory.LazyFunction(
        lambda: timezone.make_aware(__import__("datetime").datetime(2026, 6, 1, 12, 0))
    )
    descricao_narrativa = factory.Sequence(lambda n: f"Narrativa da atividade {n}")
    status = "planejado"
    ativo = True


# ---------------------------------------------------------------------------
# Budget factories
# ---------------------------------------------------------------------------

class BudgetRubricaFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BudgetRubrica
        django_get_or_create = ("slug",)

    nome = factory.Sequence(lambda n: f"Rubrica {n}")
    slug = factory.Sequence(lambda n: f"rubrica-{n}")
    ativo = True
    ordem = factory.Sequence(lambda n: n)


class BudgetAllocationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BudgetAllocation

    meta = factory.SubFactory(WorkPlanMetaFactory)
    rubrica = factory.SubFactory(BudgetRubricaFactory)
    nivel = BudgetAllocation.Nivel.TERRITORIAL
    estado = None
    territorio = factory.SubFactory(TerritoryFactory)
    valor_alocado = 0
    valor_comprometido = 0
    valor_executado = 0
    criado_por = factory.SubFactory(UserFactory)


class BudgetTransactionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BudgetTransaction

    allocation = factory.SubFactory(BudgetAllocationFactory)
    tipo = BudgetTransaction.Tipo.RESERVA
    valor = 100
    demanda_id = None
    justificativa = ""
    criado_por = factory.SubFactory(UserFactory)
