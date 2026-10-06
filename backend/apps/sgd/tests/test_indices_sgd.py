import pytest

from apps.sgd.models import ApprovalStep, Demand, DemandRequest

pytestmark = pytest.mark.django_db


def _indices_no_banco(model):
    from django.db import connection

    with connection.cursor() as cursor:
        return set(connection.introspection.get_constraints(cursor, model._meta.db_table))


@pytest.mark.parametrize("model, nomes", [
    (Demand, {"idx_demand_activity", "idx_demand_status_solic", "idx_demand_status_criado"}),
    (DemandRequest, {"idx_demandrequest_demanda", "idx_demreq_rubrica_autoriz"}),
    (ApprovalStep, {"idx_apprstep_demanda_criado"}),
])
def test_indices_exigidos_pela_arquitetura_existem_no_banco(model, nomes):
    assert nomes <= _indices_no_banco(model)
