"""Confirma a política RLS de sgd_demand direto no banco, fora do ORM/queryset
— conectando como `app_user` (o usuário de runtime, não o `postgres` que os
testes normalmente usam via `conftest.py`), já que RLS não vale pra
superusuário. `transaction=True` é necessário: sem isso o teste roda dentro
de uma transação que nunca commita, e uma segunda conexão nunca veria nem os
dados nem os GRANTs feitos aqui.

Nunca lê DB_USER/DB_PASSWORD do ambiente pra essa segunda conexão — no CI
(`.github/workflows/deploy.yml`) essas variáveis apontam pro `postgres`
(usado pelo resto da suíte via `conftest.py`), não pro `app_user` de
runtime; usar esse valor aqui bypassaria o RLS em silêncio. O role
`app_user` também não existe no Postgres efêmero do CI (só é criado por
`db/init/01_app_user.sql`, que só roda via docker-compose) — por isso este
teste cria o role sozinho, de forma idempotente, em vez de depender de
setup externo."""
import psycopg2
import pytest
from django.db import connection

from apps.core.tests.factories import UserFactory
from apps.sgd.tests.factories import DemandFactory
from apps.sgp.tests.factories import ActivityFactory, WorkPlanAcaoFactory

_APP_USER = "app_user"
_APP_USER_PASSWORD = "app_pass"
_TABELAS_LEITURA = ["sgd_demand", "sgp_activity", "core_municipality", "core_state", "core_territory"]


def _garantir_app_user_e_grants():
    # `_APP_USER`/`_APP_USER_PASSWORD` são constantes fixas do módulo, nunca
    # input externo — seguro interpolar direto (mesmo padrão já usado pros
    # nomes de tabela no GRANT logo abaixo).
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s;", [_APP_USER])
        if cursor.fetchone() is None:
            cursor.execute(f"CREATE ROLE {_APP_USER} LOGIN PASSWORD '{_APP_USER_PASSWORD}';")
        cursor.execute("GRANT USAGE ON SCHEMA public TO app_user;")
        for tabela in _TABELAS_LEITURA:
            cursor.execute(f"GRANT SELECT ON {tabela} TO app_user;")


def _ids_visiveis_para(*, user_id, role, territorios: str) -> set[int]:
    dsn = connection.settings_dict
    conn = psycopg2.connect(
        dbname=dsn["NAME"], host=dsn["HOST"] or "localhost", port=dsn["PORT"] or 5432,
        user=_APP_USER, password=_APP_USER_PASSWORD,
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
                                            usuario_articulador_rn, usuario_articulador_ce, usuario_ugp,
                                            usuario_fgd):
    outro_solicitante = UserFactory()
    activity_ce = ActivityFactory(
        municipio=municipio_ce, tecnico_responsavel=outro_solicitante, status="planejado",
        acao=WorkPlanAcaoFactory(),
    )
    demand_rn = DemandFactory(activity=activity_rn, solicitante=solicitante_rn, status="submetida")
    demand_ce = DemandFactory(activity=activity_ce, solicitante=outro_solicitante, status="submetida")

    _garantir_app_user_e_grants()

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

    # FGD também vê todas.
    vistos_fgd = _ids_visiveis_para(user_id=usuario_fgd.pk, role="fgd", territorios="")
    assert {demand_rn.pk, demand_ce.pk} <= vistos_fgd
