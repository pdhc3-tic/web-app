"""Confirma a política RLS de sgd_demand direto no banco, fora do ORM/queryset
— conectando como `app_user` (o usuário de runtime, não o `postgres` que os
testes normalmente usam via `conftest.py`), já que RLS não vale pra
superusuário. `transaction=True` é necessário: sem isso o teste roda dentro
de uma transação que nunca commita, e uma segunda conexão nunca veria nem os
dados nem os GRANTs feitos aqui."""
import os

import psycopg2
import pytest
from django.db import connection

from apps.core.tests.factories import UserFactory
from apps.sgd.tests.factories import DemandFactory
from apps.sgp.tests.factories import ActivityFactory, WorkPlanAcaoFactory

_TABELAS_LEITURA = ["sgd_demand", "sgp_activity", "core_municipality", "core_state", "core_territory"]


def _garantir_grants_app_user():
    with connection.cursor() as cursor:
        cursor.execute("GRANT USAGE ON SCHEMA public TO app_user;")
        for tabela in _TABELAS_LEITURA:
            cursor.execute(f"GRANT SELECT ON {tabela} TO app_user;")


def _ids_visiveis_para(*, user_id, role, territorios: str) -> set[int]:
    dsn = connection.settings_dict
    conn = psycopg2.connect(
        dbname=dsn["NAME"], host=dsn["HOST"] or "localhost", port=dsn["PORT"] or 5432,
        user=os.getenv("DB_USER", "app_user"), password=os.getenv("DB_PASSWORD", "app_pass"),
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute("SET LOCAL app.current_user_id = %s;", [str(user_id)])
            cursor.execute("SET LOCAL app.user_role = %s;", [role])
            cursor.execute("SET LOCAL app.user_territorios = %s;", [territorios])
            cursor.execute("SELECT id FROM sgd_demand ORDER BY id;")
            return {row[0] for row in cursor.fetchall()}
    finally:
        conn.rollback()
        conn.close()


@pytest.mark.django_db(transaction=True)
def test_rls_filtra_por_territorio_e_papel(activity_rn, solicitante_rn, municipio_ce,
                                            usuario_articulador_rn, usuario_articulador_ce, usuario_ugp):
    outro_solicitante = UserFactory()
    activity_ce = ActivityFactory(
        municipio=municipio_ce, tecnico_responsavel=outro_solicitante, status="planejado",
        acao=WorkPlanAcaoFactory(),
    )
    demand_rn = DemandFactory(activity=activity_rn, solicitante=solicitante_rn, status="submetida")
    demand_ce = DemandFactory(activity=activity_ce, solicitante=outro_solicitante, status="submetida")

    _garantir_grants_app_user()

    # Solicitante só vê a própria demanda.
    assert _ids_visiveis_para(user_id=solicitante_rn.pk, role="adt-acr", territorios="") == {demand_rn.pk}

    # Articulador do RN vê a demanda do seu estado, não a de CE.
    vistos_rn = _ids_visiveis_para(
        user_id=usuario_articulador_rn.pk, role="articulador-estadual",
        territorios=str(activity_rn.municipio.territory_id),
    )
    assert demand_rn.pk in vistos_rn
    assert demand_ce.pk not in vistos_rn

    # Articulador do CE — o inverso.
    vistos_ce = _ids_visiveis_para(
        user_id=usuario_articulador_ce.pk, role="articulador-estadual",
        territorios=str(activity_ce.municipio.territory_id),
    )
    assert demand_ce.pk in vistos_ce
    assert demand_rn.pk not in vistos_ce

    # UGP vê todas, de qualquer território.
    vistos_ugp = _ids_visiveis_para(user_id=usuario_ugp.pk, role="ugp", territorios="")
    assert {demand_rn.pk, demand_ce.pk} <= vistos_ugp
