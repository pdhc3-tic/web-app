"""
Testes do soft-delete unificado (Issue #267).

Cobre a tabela de testes da issue: manager padrão exclui inativos,
`all_objects` dá acesso completo, o rename `ativa -> ativo` preserva dados,
`has_evidencias()` mantém o comportamento e o endpoint de histórico da UPF
continua enxergando UPFs inativas.
"""
import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from apps.core.tests.factories import MunicipalityFactory, TerritoryFactory
from apps.sgp.models import Activity, ActivityDocument, ActivityPhoto, MembroFamilia, UPF
from apps.sgp.tests.factories import ActivityFactory, ProjetoFactory, UPFFactory

pytestmark = pytest.mark.django_db


class TestManagerPadraoExcluiInativos:
    def test_upf(self, municipio_rn, projeto):
        UPFFactory(municipio=municipio_rn, projeto=projeto, ativo=True)
        UPFFactory(municipio=municipio_rn, projeto=projeto, ativo=False)
        assert UPF.objects.count() == 1
        assert UPF.objects.get().ativo is True

    def test_activity(self, municipio_rn):
        ActivityFactory(municipio=municipio_rn, ativo=True)
        ActivityFactory(municipio=municipio_rn, ativo=False)
        assert Activity.objects.count() == 1
        assert Activity.objects.get().ativo is True

    def test_activity_photo(self, municipio_rn):
        atividade = ActivityFactory(municipio=municipio_rn)
        ActivityPhoto.objects.create(
            activity=atividade,
            arquivo_key="k/ativa.jpg",
            arquivo_url="https://cdn.example.com/ativa.jpg",
            ordem=0,
            ativo=True,
        )
        ActivityPhoto.objects.create(
            activity=atividade,
            arquivo_key="k/inativa.jpg",
            arquivo_url="https://cdn.example.com/inativa.jpg",
            ordem=1,
            ativo=False,
        )
        assert ActivityPhoto.objects.count() == 1
        assert ActivityPhoto.objects.get().ativo is True

    def test_activity_document(self, municipio_rn):
        atividade = ActivityFactory(municipio=municipio_rn)
        ActivityDocument.objects.create(
            activity=atividade,
            arquivo_key="k/ativo.pdf",
            arquivo_url="https://cdn.example.com/ativo.pdf",
            tipo=ActivityDocument.TIPO_ATA,
            nome_original="ata.pdf",
            data_documento="2026-06-01",
            ativo=True,
        )
        ActivityDocument.objects.create(
            activity=atividade,
            arquivo_key="k/inativo.pdf",
            arquivo_url="https://cdn.example.com/inativo.pdf",
            tipo=ActivityDocument.TIPO_ATA,
            nome_original="ata2.pdf",
            data_documento="2026-06-01",
            ativo=False,
        )
        assert ActivityDocument.objects.count() == 1
        assert ActivityDocument.objects.get().ativo is True


class TestAllObjectsTrazTudo:
    def test_upf(self, municipio_rn, projeto):
        UPFFactory(municipio=municipio_rn, projeto=projeto, ativo=True)
        UPFFactory(municipio=municipio_rn, projeto=projeto, ativo=False)
        assert UPF.all_objects.count() == 2

    def test_activity(self, municipio_rn):
        ActivityFactory(municipio=municipio_rn, ativo=True)
        ActivityFactory(municipio=municipio_rn, ativo=False)
        assert Activity.all_objects.count() == 2

    def test_activity_photo(self, municipio_rn):
        atividade = ActivityFactory(municipio=municipio_rn)
        ActivityPhoto.objects.create(
            activity=atividade, arquivo_key="k/a.jpg",
            arquivo_url="https://cdn.example.com/a.jpg", ordem=0, ativo=True,
        )
        ActivityPhoto.objects.create(
            activity=atividade, arquivo_key="k/b.jpg",
            arquivo_url="https://cdn.example.com/b.jpg", ordem=1, ativo=False,
        )
        assert ActivityPhoto.all_objects.count() == 2

    def test_activity_document(self, municipio_rn):
        atividade = ActivityFactory(municipio=municipio_rn)
        ActivityDocument.objects.create(
            activity=atividade, arquivo_key="k/a.pdf",
            arquivo_url="https://cdn.example.com/a.pdf",
            tipo=ActivityDocument.TIPO_ATA, nome_original="a.pdf",
            data_documento="2026-06-01", ativo=True,
        )
        ActivityDocument.objects.create(
            activity=atividade, arquivo_key="k/b.pdf",
            arquivo_url="https://cdn.example.com/b.pdf",
            tipo=ActivityDocument.TIPO_ATA, nome_original="b.pdf",
            data_documento="2026-06-01", ativo=False,
        )
        assert ActivityDocument.all_objects.count() == 2


class TestMigracaoPreservaDados:
    """Rename `ativa -> ativo` (UPF e ActivityPhoto): a coluna renomeada
    preserva o valor e o atributo antigo deixa de existir no model."""

    def test_upf(self, municipio_rn, projeto):
        upf = UPFFactory(municipio=municipio_rn, projeto=projeto, ativo=False)
        upf.refresh_from_db()
        assert upf.ativo is False
        assert not hasattr(upf, "ativa")

    def test_activity_photo(self, municipio_rn):
        atividade = ActivityFactory(municipio=municipio_rn)
        foto = ActivityPhoto.objects.create(
            activity=atividade, arquivo_key="k/c.jpg",
            arquivo_url="https://cdn.example.com/c.jpg", ordem=0, ativo=False,
        )
        foto.refresh_from_db()
        assert foto.ativo is False
        assert not hasattr(foto, "ativa")


class TestHasEvidenciasAposUnificacao:
    def test_sem_fotos_nem_documentos_retorna_false(self, municipio_rn):
        atividade = ActivityFactory(municipio=municipio_rn)
        assert atividade.has_evidencias() is False

    def test_com_foto_ativa_retorna_true(self, municipio_rn):
        atividade = ActivityFactory(municipio=municipio_rn)
        ActivityPhoto.objects.create(
            activity=atividade, arquivo_key="k/d.jpg",
            arquivo_url="https://cdn.example.com/d.jpg", ordem=0, ativo=True,
        )
        assert atividade.has_evidencias() is True

    def test_com_documento_ativo_retorna_true(self, municipio_rn):
        atividade = ActivityFactory(municipio=municipio_rn)
        ActivityDocument.objects.create(
            activity=atividade, arquivo_key="k/e.pdf",
            arquivo_url="https://cdn.example.com/e.pdf",
            tipo=ActivityDocument.TIPO_ATA, nome_original="e.pdf",
            data_documento="2026-06-01", ativo=True,
        )
        assert atividade.has_evidencias() is True

    def test_apenas_foto_e_documento_inativos_retorna_false(self, municipio_rn):
        atividade = ActivityFactory(municipio=municipio_rn)
        ActivityPhoto.objects.create(
            activity=atividade, arquivo_key="k/f.jpg",
            arquivo_url="https://cdn.example.com/f.jpg", ordem=0, ativo=False,
        )
        ActivityDocument.objects.create(
            activity=atividade, arquivo_key="k/g.pdf",
            arquivo_url="https://cdn.example.com/g.pdf",
            tipo=ActivityDocument.TIPO_ATA, nome_original="g.pdf",
            data_documento="2026-06-01", ativo=False,
        )
        assert atividade.has_evidencias() is False


class TestHistoricoVeInativos:
    def test_historico_de_upf_inativa_retorna_200(
        self, auth_client, upf_inativa
    ):
        response = auth_client.get(f"/api/v1/upfs/{upf_inativa.pk}/historico/")
        assert response.status_code == 200


class TestMigrationRenomeiaAtivaParaAtivoPreservandoDados(TransactionTestCase):
    """Exercita a migration de verdade (não só o schema final).

    Cria uma UPF inativa no estado anterior ao rename (`ativa`, migration
    0029), migra para frente até 0031 e confirma que o registro continua
    existindo com `ativo=False`. Complementa `TestMigracaoPreservaDados`
    (que só valida o schema atual) provando o que a issue pede — que o
    RenameField preserva os dados de um registro que já existia antes da
    migration rodar — via `MigrationExecutor`, como sugerido no review do
    PR #284.
    """

    migrate_from = [("sgp", "0029_activitydocument_deleted_at")]
    migrate_to = [("sgp", "0031_upf_ativa_para_ativo")]

    def setUp(self):
        super().setUp()
        self.territorio = TerritoryFactory()
        self.municipio = MunicipalityFactory(territory=self.territorio)
        self.projeto = ProjetoFactory()
        self.titular = MembroFamilia.objects.create(
            nome_completo="Titular Histórico",
            cpf="12345678900",
            grau_parentesco="titular",
        )

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)

        HistoricalUPF = executor.loader.project_state(self.migrate_from).apps.get_model(
            "sgp", "UPF"
        )
        self.upf_id = HistoricalUPF.objects.create(
            projeto_id=self.projeto.pk,
            municipio_id=self.municipio.pk,
            territorio_id=self.territorio.pk,
            titular_id=self.titular.pk,
            ativa=False,
        ).pk

        # Recarrega o executor: a migração para trás mudou o grafo carregado.
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        self.apps_final = executor.loader.project_state(self.migrate_to).apps

    def tearDown(self):
        # MigrationExecutor não devolve o schema ao HEAD sozinho — sem isso,
        # os próximos testes do processo rodariam contra o schema de 0031.
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_ativa_preservado_como_ativo_false(self):
        UPFFinal = self.apps_final.get_model("sgp", "UPF")
        upf = UPFFinal.objects.get(pk=self.upf_id)
        assert upf.ativo is False
        assert not hasattr(upf, "ativa")
