import factory

from apps.core.tests.factories import UserFactory
from apps.sgd.models import ApprovalStep, Demand, DemandDocument, DemandIndividualLimit, DemandRequest
from apps.sgp.tests.factories import ActivityFactory, BudgetRubricaFactory


class DemandFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Demand

    titulo = factory.Sequence(lambda n: f"Demanda {n}")
    activity = factory.SubFactory(ActivityFactory)
    justificativa = ""
    status = "rascunho"
    solicitante = factory.SubFactory(UserFactory)
    despesa_posterior = False


class DemandRequestFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DemandRequest

    demanda = factory.SubFactory(DemandFactory)
    tipo = "grafico"
    rubrica = factory.SubFactory(BudgetRubricaFactory, slug="material-grafico")
    campos_json = factory.LazyFunction(lambda: {
        "tipo_material": "banner", "quantidade": 2,
        "especificacoes_tecnicas": "2x1m, fosco", "prazo_entrega": "2026-12-01",
    })
    valor_estimado = 500
    ordem = 0


class DemandDiariaRequestFactory(DemandRequestFactory):
    tipo = "diaria"
    rubrica = factory.SubFactory(BudgetRubricaFactory, slug="diarias")
    campos_json = factory.LazyFunction(lambda: {
        "beneficiario_nome": "Fulano de Tal",
        "beneficiario_cpf": "52998224725",
        "beneficiario_cargo": "Técnico",
        "beneficiario_vinculo": "servidor_ufersa",
        "municipio_destino_id": None,
        "data_inicio": "2026-06-01",
        "data_fim": "2026-06-03",
        "meio_transporte": "rodoviario",
        "justificativa": "Visita técnica.",
    })
    valor_estimado = 0


class DemandDocumentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DemandDocument

    demanda = factory.SubFactory(DemandFactory)
    arquivo_key = factory.Sequence(lambda n: f"demandas/1/documentos/{n}.pdf")
    arquivo_url = factory.Sequence(lambda n: f"https://r2.example.com/demandas/1/documentos/{n}.pdf")
    tipo = "cotacao"
    nome_original = "cotacao.pdf"
    fornecedor = factory.Sequence(lambda n: f"Fornecedor {n}")
    content_type = "application/pdf"
    tamanho_bytes = 1024
    ativo = True
    enviado_por = factory.SubFactory(UserFactory)


class ApprovalStepFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ApprovalStep

    demanda = factory.SubFactory(DemandFactory)
    etapa = "pre_autorizacao"
    responsavel = factory.SubFactory(UserFactory)
    acao = "aprovado"
    justificativa = ""
    excedente_autorizado = False


class DemandIndividualLimitFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DemandIndividualLimit

    solicitante = factory.SubFactory(UserFactory)
    rubrica = factory.SubFactory(BudgetRubricaFactory)
    valor_limite = 10_000
    valor_comprometido = 0
    valor_executado = 0
    criado_por = factory.SubFactory(UserFactory)
