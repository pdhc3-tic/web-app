import factory

from apps.core.tests.factories import UserFactory
from apps.sgp.models import WorkPlanAcao, WorkPlanMeta


class WorkPlanMetaFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = WorkPlanMeta

    numero = factory.Sequence(lambda n: (n % 7) + 1)
    titulo = factory.Sequence(lambda n: f"Meta {n}")
    descricao = factory.Sequence(lambda n: f"Descrição da Meta {n}")
    ods_ids = factory.LazyFunction(lambda: [1, 2])
    data_inicio = factory.LazyFunction(
        lambda: __import__("datetime").date(2025, 11, 1)
    )
    data_fim = factory.LazyFunction(
        lambda: __import__("datetime").date(2027, 10, 31)
    )
    criado_por = factory.SubFactory(UserFactory)


class WorkPlanAcaoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = WorkPlanAcao

    meta = factory.SubFactory(WorkPlanMetaFactory)
    numero = factory.Sequence(lambda n: f"1.{(n % 7) + 1}")
    descricao = factory.Sequence(lambda n: f"Ação {n}")
    tipo_unidade = 11  # Família atendida
    quantidade_planejada = factory.LazyFunction(
        lambda: __import__("decimal").Decimal("100.00")
    )
    valor_unitario = factory.LazyFunction(
        lambda: __import__("decimal").Decimal("500.00")
    )
    quantidade_realizada = factory.LazyFunction(
        lambda: __import__("decimal").Decimal("0.00")
    )
