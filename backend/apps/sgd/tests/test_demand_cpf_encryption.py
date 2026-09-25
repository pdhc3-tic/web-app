import pytest
from django.db import connection

from apps.sgd.tests.factories import DemandDiariaRequestFactory

pytestmark = pytest.mark.django_db


def test_cpf_beneficiario_nao_legivel_em_texto_claro(demand_rascunho_rn, municipio_rn):
    solicitacao = DemandDiariaRequestFactory(
        demanda=demand_rascunho_rn, beneficiario_cpf="52998224725",
        campos_json={
            "beneficiario_nome": "Fulano", "beneficiario_cargo": "Técnico",
            "beneficiario_vinculo": "servidor_ufersa", "municipio_destino_id": municipio_rn.pk,
            "data_inicio": "2026-06-01", "data_fim": "2026-06-02",
            "meio_transporte": "rodoviario", "justificativa": "Visita.",
        },
    )

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT beneficiario_cpf FROM sgd_demandrequest WHERE id = %s", [solicitacao.pk],
        )
        valor_bruto = cursor.fetchone()[0]

    assert valor_bruto != "52998224725"
    assert "52998224725" not in valor_bruto

    solicitacao.refresh_from_db()
    assert solicitacao.beneficiario_cpf == "52998224725"
