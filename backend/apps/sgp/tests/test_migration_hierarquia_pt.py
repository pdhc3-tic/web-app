"""Migrations 0033–0035: Plano de Trabalho de Meta → Ação (X.Y, `tipo_unidade`)
para Meta → Submeta → Ação (X.Y.Z, Indicador), nos dois sentidos."""
from datetime import date

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

ANTES = [("sgp", "0034_exportjob_enfileirado_em")]
DEPOIS = [("sgp", "0037_acao_submeta_indicador_obrigatorios")]


class TestMigracaoHierarquiaDoPlanoDeTrabalho(TransactionTestCase):
    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate(ANTES)
        antigos = executor.loader.project_state(ANTES).apps
        Meta = antigos.get_model("sgp", "WorkPlanMeta")
        Acao = antigos.get_model("sgp", "WorkPlanAcao")

        self.meta = Meta.objects.create(
            numero=1, titulo="Organização produtiva",
            data_inicio=date(2026, 1, 1), data_fim=date(2026, 12, 31),
        )
        self.meta_sem_acoes = Meta.objects.create(
            numero=2, titulo="Sem ações",
            data_inicio=date(2026, 1, 1), data_fim=date(2026, 12, 31),
        )
        self.oficinas = Acao.objects.create(
            meta=self.meta, numero="1.1", descricao="Oficinas", tipo_unidade=2,
            quantidade_planejada=10, valor_unitario=100,
            data_inicio=date(2026, 3, 1), data_fim=date(2026, 6, 30),
        ).pk
        self.familias = Acao.objects.create(
            meta=self.meta, numero="1.2", descricao="Famílias atendidas", tipo_unidade=11,
            quantidade_planejada=50, valor_unitario=10,
        ).pk

    def tearDown(self):
        # MigrationExecutor não devolve o schema ao HEAD sozinho.
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def _migrar(self, alvo):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(alvo)
        return executor.loader.project_state(alvo).apps

    def test_para_frente_cria_submeta_renumera_e_vincula_indicador(self):
        novos = self._migrar(DEPOIS)
        Submeta = novos.get_model("sgp", "WorkPlanSubmeta")
        Acao = novos.get_model("sgp", "WorkPlanAcao")

        submeta = Submeta.objects.get(meta_id=self.meta.pk)
        assert submeta.numero == "1.1"
        assert submeta.titulo == "Organização produtiva"
        assert (submeta.data_inicio, submeta.data_fim) == (date(2026, 1, 1), date(2026, 12, 31))
        assert not Submeta.objects.filter(meta_id=self.meta_sem_acoes.pk).exists()

        oficinas = Acao.objects.select_related("indicador").get(pk=self.oficinas)
        assert oficinas.numero == "1.1.1"
        assert oficinas.submeta_id == submeta.pk
        assert oficinas.meta_id == submeta.meta_id
        assert oficinas.indicador.codigo == "IND-OFI"
        assert oficinas.data_inicio == date(2026, 3, 1)

        familias = Acao.objects.select_related("indicador").get(pk=self.familias)
        assert familias.numero == "1.1.2"
        assert familias.indicador.codigo == "IND-FAM"
        assert familias.indicador.forma_apuracao == "soma_ufpas"
        assert (familias.data_inicio, familias.data_fim) == (date(2026, 1, 1), date(2026, 12, 31))

    def test_para_tras_restaura_numero_e_tipo_unidade(self):
        self._migrar(DEPOIS)
        antigos = self._migrar(ANTES)
        Acao = antigos.get_model("sgp", "WorkPlanAcao")

        assert dict(Acao.objects.values_list("pk", "numero")) == {
            self.oficinas: "1.1", self.familias: "1.2",
        }
        assert dict(Acao.objects.values_list("pk", "tipo_unidade")) == {
            self.oficinas: 2, self.familias: 11,
        }
