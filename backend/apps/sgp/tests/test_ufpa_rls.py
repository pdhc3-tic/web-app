"""RLS de sgp_ufpa (#425) sob um papel de banco sujeito às políticas.

A suíte roda como `postgres` (conftest.py), que passa por cima da RLS. Aqui cada
cenário troca para um papel NOBYPASSRLS com `SET LOCAL ROLE` na própria
transação do teste, como `TestAgregadosIgnoramOFiltroDoRls` do orçamento: as
consultas vão direto ao banco e não dependem dos filtros em Python. Os dados são
criados antes da troca, ainda como superusuário.
"""
import csv
import io
from contextlib import contextmanager
from uuid import uuid4

import pytest
from django.db import DatabaseError, connection, transaction
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.core.db_context import (
    VARIAVEL_SISTEMA_UFPA,
    acesso_de_sistema_ufpa,
    aplicar_contexto,
    contexto_de_acesso,
    montar_contexto,
)
from apps.core.management.commands.verificar_papel_rls import problemas_do_papel_atual
from apps.core.tests.factories import MunicipalityFactory, RoleFactory, TerritoryFactory, UserFactory
from apps.sgp.budget.rls import visao_total
from apps.sgp.models import UFPA, ExportJob
from apps.sgp.services.exportacao import executar_exportacao
from apps.sgp.tests.factories import UFPAFactory

pytestmark = pytest.mark.django_db

RUNTIME = "runtime_ufpa_teste"  # nome fixo do módulo, seguro para interpolar
POLITICAS = {
    "sgp_ufpa_leitura": "SELECT",
    "sgp_ufpa_insercao": "INSERT",
    "sgp_ufpa_alteracao": "UPDATE",
    "sgp_ufpa_exclusao": "DELETE",
}


# ---------------------------------------------------------------------------
# Infraestrutura
# ---------------------------------------------------------------------------

def _garantir_papel_de_runtime():
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [RUNTIME])
        if cursor.fetchone() is None:
            cursor.execute(f"CREATE ROLE {RUNTIME} NOLOGIN NOSUPERUSER NOBYPASSRLS")
        cursor.execute(f"GRANT USAGE ON SCHEMA public TO {RUNTIME}")
        cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {RUNTIME}")
        cursor.execute(f"GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO {RUNTIME}")


def _sem_contexto():
    with connection.cursor() as cursor:
        for nome in ("app.current_user_id", "app.user_role", "app.user_territorios", VARIAVEL_SISTEMA_UFPA):
            cursor.execute("SELECT set_config(%s, '', true)", [nome])


@contextmanager
def _como_runtime(user=None):
    """Executa o bloco como o papel de runtime, com o contexto de `user` (ou
    nenhum). Volta ao superusuário no fim, mesmo se o bloco falhar."""
    with connection.cursor() as cursor:
        cursor.execute(f"SET LOCAL ROLE {RUNTIME}")
    try:
        _sem_contexto()
        if user is not None:
            aplicar_contexto(montar_contexto(user))
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute("RESET ROLE")


def _visiveis() -> set[int]:
    with connection.cursor() as cursor:
        cursor.execute("SELECT id FROM sgp_ufpa")
        return {linha[0] for linha in cursor.fetchall()}


def _tocar(ufpa_id) -> int:
    """UPDATE sem mudar território: linhas afetadas (0 = fora do USING)."""
    with connection.cursor() as cursor:
        cursor.execute("UPDATE sgp_ufpa SET atualizado_em = now() WHERE id = %s", [ufpa_id])
        return cursor.rowcount


def _mover(ufpa_id, territorio_id):
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("UPDATE sgp_ufpa SET territorio_id = %s WHERE id = %s", [territorio_id, ufpa_id])
        return cursor.rowcount


@pytest.fixture
def runtime(db):
    _garantir_papel_de_runtime()
    return _como_runtime


@pytest.fixture
def papeis(db):
    return {
        slug: RoleFactory(slug=slug, nome=slug)
        for slug in ("super-admin", "ugp", "articulador-estadual", "adt-acr", "fgd", "agricultor")
    }


@pytest.fixture
def cenario(state_rn, state_ce, territory_rn, territory_ce, outro_territorio, municipio_rn, municipio_ce,
            outro_municipio, projeto):
    """Duas UFPAs no RN (territórios diferentes) e uma no CE."""
    return {
        "rn": UFPAFactory(projeto=projeto, municipio=municipio_rn, titular_cpf="86288366757",
                          _titular_nome="Titular RN"),
        "rn_outro": UFPAFactory(projeto=projeto, municipio=outro_municipio, titular_cpf="52998224725",
                                _titular_nome="Titular RN Outro"),
        "ce": UFPAFactory(projeto=projeto, municipio=municipio_ce, titular_cpf="11144477735",
                          _titular_nome="Titular CE"),
    }


def _ids(cenario, *chaves):
    return {cenario[chave].pk for chave in chaves}


# ---------------------------------------------------------------------------
# Estrutura
# ---------------------------------------------------------------------------

def test_rls_ativa_e_politicas_criadas():
    with connection.cursor() as cursor:
        cursor.execute("SELECT relrowsecurity FROM pg_class WHERE relname = 'sgp_ufpa'")
        assert cursor.fetchone()[0] is True
        cursor.execute("SELECT policyname, cmd FROM pg_policies WHERE tablename = 'sgp_ufpa'")
        assert dict(cursor.fetchall()) == POLITICAS


def test_papel_de_runtime_sujeito_a_rls_passa_na_verificacao(runtime):
    with runtime():
        assert problemas_do_papel_atual() == []


def test_superusuario_e_apontado_pela_verificacao():
    """A suíte roda como `postgres`: exatamente o caso que o comando recusa."""
    assert any("superusuário" in problema for problema in problemas_do_papel_atual())


def _rls_de_sgp_ufpa():
    with connection.cursor() as cursor:
        cursor.execute("SELECT relrowsecurity FROM pg_class WHERE relname = 'sgp_ufpa'")
        ativa = cursor.fetchone()[0]
        cursor.execute("SELECT count(*) FROM pg_policies WHERE tablename = 'sgp_ufpa'")
        return ativa, cursor.fetchone()[0]


@pytest.mark.django_db(transaction=True)
def test_migration_reverte_e_reaplica_sem_perder_dados():
    from django.db.migrations.executor import MigrationExecutor

    ufpa = UFPAFactory(municipio=MunicipalityFactory(territory=TerritoryFactory()))
    folhas = MigrationExecutor(connection).loader.graph.leaf_nodes()
    try:
        MigrationExecutor(connection).migrate([("sgp", "0021_renomeia_upf_para_ufpa")])
        assert _rls_de_sgp_ufpa() == (False, 0)
        assert UFPA.all_objects.filter(pk=ufpa.pk).exists()
    finally:
        MigrationExecutor(connection).migrate(folhas)
    assert _rls_de_sgp_ufpa() == (True, len(POLITICAS))
    assert UFPA.all_objects.filter(pk=ufpa.pk).exists()


# ---------------------------------------------------------------------------
# Leitura por perfil
# ---------------------------------------------------------------------------

class TestLeitura:
    def test_adt_ve_so_o_proprio_territorio(self, runtime, cenario, papeis, territory_rn):
        adt = UserFactory(profiles=[(papeis["adt-acr"], territory_rn)])
        with runtime(adt):
            assert _visiveis() == _ids(cenario, "rn")

    def test_articulador_ve_o_proprio_estado(self, runtime, cenario, papeis, territory_rn):
        articulador = UserFactory(profiles=[(papeis["articulador-estadual"], territory_rn)])
        with runtime(articulador):
            assert _visiveis() == _ids(cenario, "rn", "rn_outro")

    @pytest.mark.parametrize("slug", ["ugp", "super-admin"])
    def test_perfis_globais_veem_tudo(self, runtime, cenario, papeis, slug):
        user = UserFactory(profiles=[(papeis[slug], None)])
        with runtime(user):
            assert _visiveis() == _ids(cenario, "rn", "rn_outro", "ce")

    def test_superusuario_do_django_ve_tudo(self, runtime, cenario):
        """O Django Admin entra com o usuário staff, que só é superusuário."""
        admin = UserFactory(is_superuser=True)
        with runtime(admin):
            assert _visiveis() == _ids(cenario, "rn", "rn_outro", "ce")

    @pytest.mark.parametrize("slug", ["fgd", "agricultor"])
    def test_perfis_sem_acesso_nao_veem_nada(self, runtime, cenario, papeis, slug, territory_rn):
        user = UserFactory(profiles=[(papeis[slug], territory_rn)])
        with runtime(user):
            assert _visiveis() == set()

    def test_usuario_sem_perfil_nao_ve_nada(self, runtime, cenario):
        with runtime(UserFactory()):
            assert _visiveis() == set()

    @pytest.mark.parametrize("slug", ["adt-acr", "articulador-estadual"])
    def test_vinculo_ausente_nao_vira_acesso_global(self, runtime, cenario, papeis, slug):
        user = UserFactory(profiles=[(papeis[slug], None)])
        with runtime(user):
            assert _visiveis() == set()

    def test_territorio_de_outro_perfil_nao_amplia_o_articulador(self, runtime, cenario, papeis, territory_ce):
        """O FGD vinculado ao CE não dá o CE ao Articulador sem território."""
        user = UserFactory(profiles=[(papeis["articulador-estadual"], None), (papeis["fgd"], territory_ce)])
        with runtime(user):
            assert _visiveis() == set()

    def test_multiplos_perfis_somam_os_escopos(self, runtime, cenario, papeis, territory_rn, territory_ce):
        user = UserFactory(profiles=[(papeis["articulador-estadual"], territory_rn), (papeis["adt-acr"], territory_ce)])
        with runtime(user):
            assert _visiveis() == _ids(cenario, "rn", "rn_outro", "ce")

    def test_sem_contexto_nao_ve_nada(self, runtime, cenario):
        with runtime():
            assert _visiveis() == set()

    def test_orm_tambem_e_filtrado(self, runtime, cenario, papeis, territory_rn):
        adt = UserFactory(profiles=[(papeis["adt-acr"], territory_rn)])
        with runtime(adt):
            assert set(UFPA.all_objects.values_list("pk", flat=True)) == _ids(cenario, "rn")


# ---------------------------------------------------------------------------
# Escrita
# ---------------------------------------------------------------------------

class TestEscrita:
    def test_adt_altera_no_proprio_territorio(self, runtime, cenario, papeis, territory_rn):
        adt = UserFactory(profiles=[(papeis["adt-acr"], territory_rn)])
        with runtime(adt):
            assert _tocar(cenario["rn"].pk) == 1
            assert _tocar(cenario["ce"].pk) == 0

    def test_adt_nao_move_ufpa_para_outro_territorio(self, runtime, cenario, papeis, territory_rn, territory_ce):
        adt = UserFactory(profiles=[(papeis["adt-acr"], territory_rn)])
        with runtime(adt):
            with pytest.raises(DatabaseError):
                _mover(cenario["rn"].pk, territory_ce.pk)
        cenario["rn"].refresh_from_db()
        assert cenario["rn"].territorio_id == territory_rn.pk

    def test_adt_que_atua_nos_dois_territorios_pode_mover(self, runtime, cenario, papeis, territory_rn, territory_ce):
        adt = UserFactory(profiles=[(papeis["adt-acr"], territory_rn), (papeis["adt-acr"], territory_ce)])
        with runtime(adt):
            assert _mover(cenario["rn"].pk, territory_ce.pk) == 1

    @pytest.mark.parametrize("slug", ["ugp", "articulador-estadual", "fgd"])
    def test_perfis_de_leitura_nao_alteram(self, runtime, cenario, papeis, slug, territory_rn):
        user = UserFactory(profiles=[(papeis[slug], territory_rn if slug != "ugp" else None)])
        with runtime(user):
            assert _tocar(cenario["rn"].pk) == 0

    def test_super_admin_altera_qualquer_uma(self, runtime, cenario, papeis, territory_ce):
        user = UserFactory(profiles=[(papeis["super-admin"], None)])
        with runtime(user):
            assert _tocar(cenario["ce"].pk) == 1
            assert _mover(cenario["rn"].pk, territory_ce.pk) == 1

    def test_adt_insere_no_proprio_territorio(self, runtime, papeis, territory_rn, municipio_rn, projeto):
        adt = UserFactory(profiles=[(papeis["adt-acr"], territory_rn)])
        with runtime(adt):
            ufpa = UFPAFactory(projeto=projeto, municipio=municipio_rn, titular_cpf="39053344705")
            assert ufpa.pk in _visiveis()

    def test_adt_nao_insere_em_outro_territorio(self, runtime, papeis, territory_rn, municipio_ce, projeto):
        adt = UserFactory(profiles=[(papeis["adt-acr"], territory_rn)])
        with runtime(adt):
            with pytest.raises(DatabaseError), transaction.atomic():
                UFPAFactory(projeto=projeto, municipio=municipio_ce, titular_cpf="39053344705")

    @pytest.mark.parametrize("slug", ["ugp", "articulador-estadual"])
    def test_perfis_de_leitura_nao_inserem(self, runtime, papeis, slug, territory_rn, municipio_rn, projeto):
        user = UserFactory(profiles=[(papeis[slug], territory_rn if slug != "ugp" else None)])
        with runtime(user):
            with pytest.raises(DatabaseError), transaction.atomic():
                UFPAFactory(projeto=projeto, municipio=municipio_rn, titular_cpf="39053344705")

    def test_adt_nao_exclui_fora_do_territorio(self, runtime, cenario, papeis, territory_rn):
        adt = UserFactory(profiles=[(papeis["adt-acr"], territory_rn)])
        with runtime(adt), connection.cursor() as cursor:
            cursor.execute("DELETE FROM sgp_ufpa WHERE id = %s", [cenario["ce"].pk])
            assert cursor.rowcount == 0


# ---------------------------------------------------------------------------
# Contexto: elevações, troca de usuário, restauração após erro
# ---------------------------------------------------------------------------

class TestContexto:
    def test_visao_total_do_orcamento_nao_amplia_ufpas(self, runtime, cenario, papeis, territory_rn):
        adt = UserFactory(profiles=[(papeis["adt-acr"], territory_rn)])
        with runtime(adt):
            with visao_total():
                assert _visiveis() == _ids(cenario, "rn")

    def test_acesso_de_sistema_libera_e_restaura(self, runtime, cenario, papeis, territory_rn):
        adt = UserFactory(profiles=[(papeis["adt-acr"], territory_rn)])
        with runtime(adt):
            with acesso_de_sistema_ufpa("teste"):
                assert _visiveis() == _ids(cenario, "rn", "rn_outro", "ce")
            assert _visiveis() == _ids(cenario, "rn")

    def test_acesso_de_sistema_restaura_apos_erro(self, runtime, cenario, papeis, territory_rn):
        adt = UserFactory(profiles=[(papeis["adt-acr"], territory_rn)])
        with runtime(adt):
            with pytest.raises(RuntimeError):
                with acesso_de_sistema_ufpa("teste"):
                    raise RuntimeError
            assert _visiveis() == _ids(cenario, "rn")

    def test_troca_de_usuario_nao_herda_o_anterior(self, runtime, cenario, papeis, territory_rn, territory_ce):
        adt_rn = UserFactory(profiles=[(papeis["adt-acr"], territory_rn)])
        adt_ce = UserFactory(profiles=[(papeis["adt-acr"], territory_ce)])
        with runtime():
            with contexto_de_acesso(adt_rn):
                assert _visiveis() == _ids(cenario, "rn")
            with contexto_de_acesso(adt_ce):
                assert _visiveis() == _ids(cenario, "ce")
            # Fim do bloco: volta ao contexto de antes (nenhum).
            assert _visiveis() == set()

    def test_contexto_de_acesso_restaura_apos_erro(self, runtime, cenario, papeis, territory_rn):
        adt = UserFactory(profiles=[(papeis["adt-acr"], territory_rn)])
        with runtime():
            with pytest.raises(RuntimeError):
                with contexto_de_acesso(adt):
                    assert _visiveis() == _ids(cenario, "rn")
                    raise RuntimeError
            assert _visiveis() == set()

    def test_contexto_de_acesso_nao_herda_elevacao_de_sistema(self, runtime, cenario, papeis, territory_rn):
        adt = UserFactory(profiles=[(papeis["adt-acr"], territory_rn)])
        with runtime():
            with acesso_de_sistema_ufpa("teste"):
                with contexto_de_acesso(adt):
                    assert _visiveis() == _ids(cenario, "rn")


# ---------------------------------------------------------------------------
# Exportação assíncrona
# ---------------------------------------------------------------------------

def _titulares_do_csv(conteudo: bytes) -> set[str]:
    leitor = csv.DictReader(io.StringIO(bytes(conteudo).decode("utf-8-sig")))
    return {linha["Titular"] for linha in leitor}


def test_exportacao_assincrona_gera_o_escopo_do_solicitante(runtime, cenario, papeis, territory_rn):
    """O worker não passa pelo middleware. Sem o contexto do solicitante, o
    arquivo sairia vazio; com um contexto errado, ampliado."""
    articulador = UserFactory(profiles=[(papeis["articulador-estadual"], territory_rn)])
    job = ExportJob.objects.create(
        tipo=ExportJob.Tipo.UFPAS, formato=ExportJob.Formato.CSV, filtros={}, solicitante=articulador,
    )

    with runtime():  # como o worker: papel de runtime, sem contexto nenhum
        executar_exportacao(job.pk)

    job.refresh_from_db()
    assert job.status == ExportJob.Status.CONCLUIDA, job.erro
    assert _titulares_do_csv(job.conteudo) == {"Titular RN", "Titular RN Outro"}
    assert job.total_registros == 2


# ---------------------------------------------------------------------------
# SCA com a política ativa
# ---------------------------------------------------------------------------

def _cliente_jwt(user):
    """Token de verdade: com `force_authenticate`, o SessionContextMiddleware
    não monta o contexto de banco."""
    cliente = APIClient()
    cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return cliente


def _push(cliente, payload, *, uuid_local=None):
    from apps.sca.tests.test_sync_push import build_item, post_batch

    resposta = post_batch(cliente, [build_item(payload=payload, uuid_local=uuid_local)])
    assert resposta.status_code == 200, resposta.data
    return resposta.data["resultados"][0]


def _payload(projeto, municipio, cpf):
    return {
        "projeto": projeto.pk,
        "municipio": municipio.pk,
        "territorio": municipio.territory_id,
        "titular": {"nome_completo": "Titular SCA", "cpf": cpf},
    }


class TestSca:
    def test_push_cria_ufpa_no_proprio_territorio(self, runtime, papeis, territory_rn, municipio_rn, projeto):
        adt = UserFactory(profiles=[(papeis["adt-acr"], territory_rn)])
        with runtime():
            resultado = _push(_cliente_jwt(adt), _payload(projeto, municipio_rn, "39053344705"))
        assert resultado["status"] == "ok", resultado
        assert UFPA.all_objects.filter(pk=resultado["id_servidor"], territorio=territory_rn).exists()

    def test_duplicidade_fora_do_territorio_e_identificada(self, runtime, cenario, papeis, territory_rn, municipio_rn,
                                                           projeto):
        """O CPF já é titular da UFPA do CE: sem a elevação, a busca não acharia
        a linha e o push tentaria criar de novo, batendo na constraint."""
        adt = UserFactory(profiles=[(papeis["adt-acr"], territory_rn)])
        with runtime():
            resultado = _push(_cliente_jwt(adt), _payload(projeto, municipio_rn, "11144477735"))
        assert resultado["status"] == "erro"
        assert resultado["erro"] == "FORA_TERRITORIO"

    def test_replay_de_uuid_fora_do_territorio_e_identificado(self, runtime, cenario, papeis, territory_rn,
                                                             municipio_rn, projeto):
        ufpa_ce = cenario["ce"]
        ufpa_ce.uuid_local = uuid4()
        ufpa_ce.save(update_fields=["uuid_local"])
        adt = UserFactory(profiles=[(papeis["adt-acr"], territory_rn)])
        with runtime():
            resultado = _push(
                _cliente_jwt(adt), _payload(projeto, municipio_rn, "39053344705"), uuid_local=ufpa_ce.uuid_local,
            )
        assert resultado["status"] == "erro"
        assert resultado["erro"] == "FORA_TERRITORIO"

    def test_articulador_resolve_conflito_de_ufpa(self, runtime, cenario, papeis, territory_rn):
        """O Articulador só lê UFPAs, mas resolve conflitos: a gravação roda como
        operação de sistema depois da autorização do `get_object()`."""
        from apps.sca.models import ConflictLog
        from apps.sca.tests.factories import ConflictLogFactory

        ufpa = cenario["rn"]
        ufpa.uuid_local = uuid4()
        ufpa.save(update_fields=["uuid_local"])
        articulador = UserFactory(profiles=[(papeis["articulador-estadual"], territory_rn)])
        conflito = ConflictLogFactory(
            entidade="ufpa", uuid_local=str(ufpa.uuid_local), campo="apelido",
            valor_local="Apelido do campo", valor_servidor="Apelido do servidor",
            estrategia=ConflictLog.Estrategia.LAST_WRITE_WINS, campo_sensivel=False,
            status=ConflictLog.Status.PENDENTE, territorio=territory_rn,
        )

        with runtime():
            resposta = _cliente_jwt(articulador).post(
                f"/api/v1/sca/conflicts/{conflito.pk}/resolver/", data={"decisao": "local"}, format="json",
            )

        assert resposta.status_code == 200, resposta.data
        ufpa.refresh_from_db()
        assert ufpa.apelido == "Apelido do campo"

    def test_articulador_sem_territorio_nao_resolve_conflito(self, runtime, cenario, papeis, territory_rn):
        """`IsArticuladorEstadual` usa `user_states()`, onde sem território são
        todos os estados. Como a resolução grava sob a elevação de sistema, ela
        exige o critério do SGP: estados do próprio perfil, sem vínculo nenhum."""
        from apps.sca.models import ConflictLog
        from apps.sca.tests.factories import ConflictLogFactory

        ufpa = cenario["rn"]
        ufpa.uuid_local = uuid4()
        ufpa.save(update_fields=["uuid_local"])
        apelido_original = ufpa.apelido
        articulador = UserFactory(profiles=[(papeis["articulador-estadual"], None)])
        conflito = ConflictLogFactory(
            entidade="ufpa", uuid_local=str(ufpa.uuid_local), campo="apelido",
            valor_local="Apelido do campo", valor_servidor="Apelido do servidor",
            estrategia=ConflictLog.Estrategia.LAST_WRITE_WINS, campo_sensivel=False,
            status=ConflictLog.Status.PENDENTE, territorio=territory_rn,
        )

        with runtime():
            resposta = _cliente_jwt(articulador).post(
                f"/api/v1/sca/conflicts/{conflito.pk}/resolver/", data={"decisao": "local"}, format="json",
            )

        assert resposta.status_code == 403
        ufpa.refresh_from_db()
        assert ufpa.apelido == apelido_original
        conflito.refresh_from_db()
        assert conflito.status == ConflictLog.Status.PENDENTE

    def test_push_de_quem_so_le_e_recusado_sem_derrubar_o_batch(self, runtime, papeis, territory_rn, municipio_rn,
                                                               projeto):
        """A UGP alcança todos os territórios no SCA, mas só lê UFPAs."""
        from apps.sca.tests.test_sync_push import build_item, post_batch

        ugp = UserFactory(profiles=[(papeis["ugp"], None)])
        itens = [
            build_item(payload=_payload(projeto, municipio_rn, "39053344705")),
            build_item(payload=_payload(projeto, municipio_rn, "11144477735")),
        ]
        with runtime():
            resposta = post_batch(_cliente_jwt(ugp), itens)

        assert resposta.status_code == 200
        assert [r["status"] for r in resposta.data["resultados"]] == ["erro", "erro"]
        assert all(r["erro"].startswith("SEM_PERMISSAO_ESCRITA") for r in resposta.data["resultados"])
        assert not UFPA.all_objects.filter(titular__cpf__in=["39053344705", "11144477735"]).exists()

    def test_push_de_varios_perfis_so_grava_no_territorio_do_adt(self, runtime, cenario, papeis, territory_rn,
                                                                 territory_ce, municipio_rn, projeto):
        """Articulador do RN com ADT/ACR do CE: o SCA alcança os dois
        territórios, mas a escrita vale só no CE."""
        from apps.sca.tests.test_sync_push import build_item, post_batch

        user = UserFactory(profiles=[(papeis["articulador-estadual"], territory_rn), (papeis["adt-acr"], territory_ce)])
        ufpa_rn = cenario["rn"]
        ufpa_rn.uuid_local = uuid4()
        ufpa_rn.save(update_fields=["uuid_local"])
        base = {"apelido": ufpa_rn.apelido or ""}
        item = build_item(
            operacao="update", uuid_local=ufpa_rn.uuid_local, payload={"apelido": "Alterado"}, base=base,
        )

        with runtime():
            resposta = post_batch(_cliente_jwt(user), [item])

        assert resposta.status_code == 200
        resultado = resposta.data["resultados"][0]
        assert resultado["status"] == "erro"
        assert resultado["erro"].startswith(("SEM_PERMISSAO_ESCRITA", "FORA_TERRITORIO"))
        ufpa_rn.refresh_from_db()
        assert ufpa_rn.apelido != "Alterado"

    def test_adt_nao_move_ufpa_para_outro_territorio_pelo_push(self, runtime, cenario, papeis, territory_rn,
                                                              municipio_ce, projeto):
        from apps.sca.tests.test_sync_push import build_item, post_batch

        adt = UserFactory(profiles=[(papeis["adt-acr"], territory_rn)])
        ufpa_rn = cenario["rn"]
        ufpa_rn.uuid_local = uuid4()
        ufpa_rn.save(update_fields=["uuid_local"])
        item = build_item(
            operacao="update", uuid_local=ufpa_rn.uuid_local,
            payload={"municipio": municipio_ce.pk}, base={"municipio": ufpa_rn.municipio_id},
        )

        with runtime():
            resposta = post_batch(_cliente_jwt(adt), [item])

        assert resposta.data["resultados"][0]["erro"].startswith("SEM_PERMISSAO_ESCRITA")
        ufpa_rn.refresh_from_db()
        assert ufpa_rn.territorio_id == territory_rn.pk

    def test_recusa_do_banco_vira_erro_do_item_e_nao_500(self, runtime, papeis, municipio_rn, projeto, monkeypatch):
        """Defesa em profundidade: se a checagem em Python deixar passar, a
        recusa da RLS fica restrita ao item."""
        from apps.sca.sync_entities import UFPASyncEntity

        monkeypatch.setattr(UFPASyncEntity, "pode_escrever", lambda self, user, data, instance=None: True)
        ugp = UserFactory(profiles=[(papeis["ugp"], None)])
        with runtime():
            resultado = _push(_cliente_jwt(ugp), _payload(projeto, municipio_rn, "39053344705"))

        assert resultado["status"] == "erro"
        assert resultado["erro"].startswith("ERRO_INTERNO")

    def test_pull_traz_so_o_territorio_do_adt(self, runtime, cenario, papeis, territory_rn):
        from apps.sca.tests.test_sync_pull import get_pull

        adt = UserFactory(profiles=[(papeis["adt-acr"], territory_rn)])
        with runtime():
            resposta = get_pull(_cliente_jwt(adt))

        assert resposta.status_code == 200
        assert {u["id"] for u in resposta.data["ufpas"]} == _ids(cenario, "rn")

    def test_push_cria_membro_na_ufpa_do_proprio_territorio(self, runtime, cenario, papeis, territory_rn):
        from apps.sca.tests.test_sync_push import build_item
        from apps.sgp.models import MembroFamilia

        adt = UserFactory(profiles=[(papeis["adt-acr"], territory_rn)])
        dentro = build_item(
            entidade="member",
            payload={"ufpa": cenario["rn"].pk, "nome_completo": "Filho RN", "grau_parentesco": "filho"},
        )
        fora = build_item(
            entidade="member",
            payload={"ufpa": cenario["ce"].pk, "nome_completo": "Filho CE", "grau_parentesco": "filho"},
        )
        with runtime():
            resposta = _cliente_jwt(adt).post(
                "/api/v1/sca/sync/push/", data={"registros": [dentro, fora], "device_id": "dev-001"}, format="json",
            )

        assert resposta.status_code == 200
        assert [r["status"] for r in resposta.data["resultados"]] == ["ok", "erro"]
        assert MembroFamilia.objects.filter(nome_completo="Filho RN", ufpa=cenario["rn"]).exists()
        assert not MembroFamilia.objects.filter(nome_completo="Filho CE").exists()


# ---------------------------------------------------------------------------
# API HTTP, mapa e Admin passando pelo SessionContextMiddleware
# ---------------------------------------------------------------------------

UFPAS_URL = "/api/v1/sgp/ufpas/"


class TestApiComRls:
    def test_listagem_por_perfil(self, runtime, cenario, papeis, territory_rn):
        adt = UserFactory(profiles=[(papeis["adt-acr"], territory_rn)])
        articulador = UserFactory(profiles=[(papeis["articulador-estadual"], territory_rn)])
        with runtime():
            ids_adt = {u["id"] for u in _cliente_jwt(adt).get(UFPAS_URL).data["results"]}
            ids_articulador = {u["id"] for u in _cliente_jwt(articulador).get(UFPAS_URL).data["results"]}

        assert ids_adt == _ids(cenario, "rn")
        assert ids_articulador == _ids(cenario, "rn", "rn_outro")

    def test_mapa_respeita_o_escopo(self, runtime, cenario, papeis, territory_rn):
        for ufpa in cenario.values():
            UFPA.all_objects.filter(pk=ufpa.pk).update(latitude="-5.1", longitude="-37.3")
        adt = UserFactory(profiles=[(papeis["adt-acr"], territory_rn)])
        with runtime():
            resposta = _cliente_jwt(adt).get(f"{UFPAS_URL}mapa/")

        assert resposta.status_code == 200
        assert {f["properties"]["id"] for f in resposta.data["features"]} == _ids(cenario, "rn")

    def test_perfil_de_leitura_recebe_403_ao_escrever(self, runtime, cenario, papeis, territory_rn, municipio_rn,
                                                     projeto):
        ugp = UserFactory(profiles=[(papeis["ugp"], None)])
        with runtime():
            cliente = _cliente_jwt(ugp)
            criacao = cliente.post(
                UFPAS_URL, {"projeto": projeto.pk, "nome": "Nova", "cpf": "39053344705", "municipio": municipio_rn.pk},
                format="json",
            )
            edicao = cliente.patch(f"{UFPAS_URL}{cenario['rn'].pk}/", {"apelido": "X"}, format="json")

        assert criacao.status_code == 403
        assert edicao.status_code == 403

    def test_varios_perfis_escrevem_so_no_territorio_do_adt(self, runtime, cenario, papeis, territory_ce):
        """UGP com ADT/ACR do CE lê tudo, mas só altera e desativa no CE: antes, o
        PATCH fora do território passava pelo Python e a RLS devolvia 500."""
        user = UserFactory(profiles=[(papeis["ugp"], None), (papeis["adt-acr"], territory_ce)])
        with runtime():
            cliente = _cliente_jwt(user)
            fora = cliente.patch(f"{UFPAS_URL}{cenario['rn'].pk}/", {"apelido": "Fora"}, format="json")
            desativar_fora = cliente.delete(f"{UFPAS_URL}{cenario['rn'].pk}/")
            dentro = cliente.patch(f"{UFPAS_URL}{cenario['ce'].pk}/", {"apelido": "Dentro"}, format="json")

        assert fora.status_code == 403
        assert desativar_fora.status_code == 403
        assert dentro.status_code == 200, dentro.data
        cenario["rn"].refresh_from_db()
        assert cenario["rn"].ativo is True

    def test_adt_cria_no_proprio_territorio_e_recebe_403_fora(self, runtime, papeis, territory_rn, municipio_rn,
                                                            municipio_ce, projeto):
        adt = UserFactory(profiles=[(papeis["adt-acr"], territory_rn)])
        with runtime():
            cliente = _cliente_jwt(adt)
            dentro = cliente.post(
                UFPAS_URL, {"projeto": projeto.pk, "nome": "Dentro", "cpf": "39053344705", "municipio": municipio_rn.pk},
                format="json",
            )
            fora = cliente.post(
                UFPAS_URL, {"projeto": projeto.pk, "nome": "Fora", "cpf": "11144477735", "municipio": municipio_ce.pk},
                format="json",
            )

        assert dentro.status_code == 201, dentro.data
        assert fora.status_code == 403

    def test_admin_do_django_lista_todas(self, runtime, cenario):
        from django.test import Client

        admin = UserFactory(is_superuser=True)
        cliente = Client()
        cliente.force_login(admin)
        with runtime():
            resposta = cliente.get("/admin/sgp/ufpa/")

        assert resposta.status_code == 200
        assert resposta.context["cl"].result_count == 3

    def test_detalhe_da_atividade_mostra_so_participantes_visiveis(self, runtime, cenario, papeis, territory_rn,
                                                                  municipio_rn):
        """A atividade é do território do ADT, mas uma das UFPAs participantes é
        do CE: ela e os membros dela ficam fora da resposta, como na RLS."""
        from apps.sgp.tests.factories import ActivityFactory, MembroFactory

        adt = UserFactory(profiles=[(papeis["adt-acr"], territory_rn)])
        atividade = ActivityFactory(municipio=municipio_rn, tecnico_responsavel=adt)
        atividade.ufpas_participantes.set([cenario["rn"], cenario["ce"]])
        membro_rn = MembroFactory(ufpa=cenario["rn"], nome_completo="Membro RN", grau_parentesco="filho")
        membro_ce = MembroFactory(ufpa=cenario["ce"], nome_completo="Membro CE", grau_parentesco="filho")
        atividade.membros_participantes.set([membro_rn, membro_ce])

        with runtime():
            resposta = _cliente_jwt(adt).get(f"/api/v1/sgp/atividades/{atividade.pk}/")

        assert resposta.status_code == 200, resposta.data
        assert {u["id"] for u in resposta.data["ufpas_participantes"]} == _ids(cenario, "rn")
        assert {m["id"] for m in resposta.data["membros_participantes"]} == {membro_rn.pk}
        # A tabela de ligação não passa pela RLS: as contagens agregadas seguem completas.
        assert atividade.ufpas_participantes.through.objects.filter(activity_id=atividade.pk).count() == 2
