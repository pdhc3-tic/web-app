from datetime import date
from decimal import Decimal
from uuid import uuid4

import factory
from django.utils import timezone

from apps.core.tests.factories import (
    MunicipalityFactory,
    OrganizationFactory,
    TerritoryFactory,
    UserFactory,
)
from apps.sgp.budget import limites
from apps.sgp.models import (
    Activity,
    BudgetPool,
    BudgetRubrica,
    BudgetTransaction,
    Comunidade,
    Cultura,
    EspecieAnimal,
    FormResponse,
    MembroFamilia,
    Production,
    Projeto,
    Tecnico,
    UFPA,
    UFPADocument,    SpendingLimit,
    TED,
    TEDVersion,
    TEDVersionRubrica,
)
from apps.sgp.models.indicator import Indicator
from apps.sgp.models.workplan import WorkPlanAcao, WorkPlanMeta, WorkPlanSubmeta


class ProjetoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Projeto

    nome = factory.Sequence(lambda n: f"Projeto {n}")
    descricao = factory.Sequence(lambda n: f"Descrição do Projeto {n}")
    ativo = True


class UFPAFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = UFPA

    _titular_nome = factory.Sequence(lambda n: f"Titular {n}")
    _titular_cpf = factory.Sequence(lambda n: f"{n:011d}")
    projeto = factory.SubFactory(ProjetoFactory)
    municipio = factory.SubFactory(MunicipalityFactory)
    territorio = factory.SelfAttribute("municipio.territory")
    ativo = True

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        titular_nome = kwargs.pop("_titular_nome")
        titular_cpf = kwargs.pop("cpf", kwargs.pop("titular_cpf", kwargs.pop("_titular_cpf")))
        titular = MembroFamilia(
            ufpa=None,
            grau_parentesco="titular",
            nome_completo=titular_nome,
            cpf=titular_cpf,
            data_nascimento="1990-01-01",
        )
        titular.save()
        kwargs["titular"] = titular
        ufpa = super()._create(model_class, *args, **kwargs)
        titular.ufpa = ufpa
        titular.save(update_fields=["ufpa"])
        return ufpa


class MembroFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MembroFamilia

    ufpa = factory.SubFactory("apps.sgp.tests.factories.UFPAFactory")
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


class UFPADocumentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = UFPADocument

    ufpa = factory.SubFactory(UFPAFactory)
    tipo = UFPADocument.TIPO_DAP_CAF
    descricao = "Documento da UFPA"
    arquivo_key = factory.LazyAttributeSequence(
        lambda obj, n: (
            f"ufpas/{obj.ufpa.pk}/documentos/"
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

    ufpa = factory.SubFactory(UFPAFactory)
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

    ufpa = factory.SubFactory(UFPAFactory)
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


class IndicatorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Indicator

    # Prefixo próprio: a migration 0034 já cria o catálogo IND-* no banco de teste.
    codigo = factory.Sequence(lambda n: f"TST-{n:04d}")
    nome = factory.Sequence(lambda n: f"Indicador {n}")
    unidade_medida = "evento"
    forma_apuracao = "contagem_atividades"
    ativo = True


class WorkPlanSubmetaFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = WorkPlanSubmeta

    meta = factory.SubFactory(WorkPlanMetaFactory)
    # Sequencial alto para não colidir com os números explícitos dos testes (1.1, 1.2…).
    numero = factory.LazyAttributeSequence(lambda o, n: f"{o.meta.numero}.{n + 1000}")
    titulo = factory.Sequence(lambda n: f"Submeta {n}")
    data_inicio = factory.SelfAttribute("meta.data_inicio")
    data_fim = factory.SelfAttribute("meta.data_fim")


class WorkPlanAcaoFactory(factory.django.DjangoModelFactory):
    """Com `meta=` e sem `submeta=`, cria uma Submeta nessa Meta. A Meta
    gravada na Ação sempre vem da Submeta."""

    class Meta:
        model = WorkPlanAcao

    meta = factory.SubFactory(WorkPlanMetaFactory)
    submeta = factory.SubFactory(WorkPlanSubmetaFactory, meta=factory.SelfAttribute("..meta"))
    indicador = factory.SubFactory(IndicatorFactory)
    numero = factory.LazyAttributeSequence(lambda o, n: f"{o.submeta.numero}.{n + 1000}")
    descricao = factory.Sequence(lambda n: f"Ação {n}")
    quantidade_planejada = 10
    valor_unitario = 100
    data_inicio = factory.SelfAttribute("submeta.data_inicio")
    data_fim = factory.SelfAttribute("submeta.data_fim")


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

    @factory.post_generation
    def parceiros_organizacoes(self, create, extracted, **kwargs):
        if not create or not extracted:
            return
        self.parceiros_organizacoes.set(extracted)


# ---------------------------------------------------------------------------
# Tecnico factory
# ---------------------------------------------------------------------------

class TecnicoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Tecnico

    user = factory.SubFactory(UserFactory)
    territorio = factory.SubFactory(TerritoryFactory)
    osc = factory.SubFactory(OrganizationFactory)
    papel = "adt-acr"
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


class BudgetPoolFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BudgetPool

    rubrica = factory.SubFactory(BudgetRubricaFactory)
    nivel = BudgetPool.Nivel.TERRITORIAL
    estado = None
    territorio = factory.SubFactory(TerritoryFactory)
    valor_alocado = 0
    valor_comprometido = 0
    valor_executado = 0
    reserva_ugp = False
    criado_por = factory.SubFactory(UserFactory)


class SpendingLimitFactory(factory.django.DjangoModelFactory):
    """Sobrescrita individual do período vigente."""

    class Meta:
        model = SpendingLimit

    escopo = SpendingLimit.Escopo.INDIVIDUAL
    user = factory.SubFactory(UserFactory)
    rubrica = factory.SubFactory(BudgetRubricaFactory)
    valor_limite = 10_000
    valor_comprometido = 0
    valor_executado = 0
    justificativa = "Definido no teste."
    periodo_inicio = factory.LazyFunction(lambda: limites.periodo_de(limites.hoje())[0])
    periodo_fim = factory.LazyFunction(lambda: limites.periodo_de(limites.hoje())[1])
    criado_por = factory.SubFactory(UserFactory)


class BudgetTransactionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BudgetTransaction

    pool = factory.SubFactory(BudgetPoolFactory)
    tipo = BudgetTransaction.Tipo.RESERVA
    valor = 100
    demanda_id = None
    justificativa = ""
    criado_por = factory.SubFactory(UserFactory)


# ---------------------------------------------------------------------------
# TED
# ---------------------------------------------------------------------------

class TEDFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TED

    numero = factory.Sequence(lambda n: f"TED {n}/2025")
    participes = factory.LazyFunction(lambda: ["MDA", "UFERSA"])
    objeto = "Projeto Dom Helder Câmara III"


class TEDVersionFactory(factory.django.DjangoModelFactory):
    """Já vira a versão vigente do TED, com o valor global e a vigência copiados."""

    class Meta:
        model = TEDVersion
        skip_postgeneration_save = True

    ted = factory.SubFactory(TEDFactory)
    numero_versao = 1
    tipo = TEDVersion.Tipo.ORIGINAL
    vigencia_inicio = date(2025, 11, 1)
    vigencia_fim = date(2028, 10, 31)
    valor_global = Decimal("0")
    documento_key = factory.LazyFunction(lambda: f"ted/documentos/{uuid4()}.pdf")

    @factory.post_generation
    def vigente(self, create, extracted, **kwargs):
        if not create or extracted is False:
            return
        ted = self.ted
        ted.versao_vigente = self
        ted.valor_global = self.valor_global
        ted.vigencia_inicio = self.vigencia_inicio
        ted.vigencia_fim = self.vigencia_fim
        ted.save(update_fields=["versao_vigente", "valor_global", "vigencia_inicio", "vigencia_fim"])


def aprovar_no_ted(rubrica, valor=Decimal("1000000")) -> TEDVersion:
    """Aprova `valor` para a rubrica na versão vigente, criando o TED se faltar."""
    ted = TED.objects.select_related("versao_vigente").first()
    versao = ted.versao_vigente if ted and ted.versao_vigente_id else TEDVersionFactory(
        **({"ted": ted} if ted else {})
    )
    TEDVersionRubrica.objects.create(versao=versao, rubrica=rubrica, valor_aprovado=valor)
    return versao

