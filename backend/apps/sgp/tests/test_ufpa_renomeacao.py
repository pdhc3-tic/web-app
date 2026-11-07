"""Renomeação de UPF para UFPA: rotas antigas por um ciclo e dados gravados com o nome antigo."""
import importlib

import pytest
from django.apps import apps
from django.urls import reverse

from apps.core.tests.factories import AuditLogFactory
from apps.sca.models import ConflictLog
from apps.sca.tests.factories import ConflictLogFactory
from apps.sgp.models import ExportJob
from apps.sgp.tests.factories import MembroFactory, UFPAFactory

pytestmark = pytest.mark.django_db

CANONICA = "/api/v1/sgp/ufpas/"
ALIASES = ["/api/v1/upfs/", "/api/v1/sgp/upfs/"]

migration_sgp = importlib.import_module("apps.sgp.migrations.0021_renomeia_upf_para_ufpa")
migration_sca = importlib.import_module("apps.sca.migrations.0007_conflitos_com_a_entidade_ufpa")


class TestRotas:
    def test_canonica_responde_sem_aviso_de_depreciacao(self, auth_client):
        UFPAFactory()

        resposta = auth_client.get(CANONICA)

        assert resposta.status_code == 200
        assert resposta.data["count"] == 1
        assert "Deprecation" not in resposta

    @pytest.mark.parametrize("prefixo", ALIASES)
    def test_alias_responde_o_mesmo_e_avisa_a_depreciacao(self, auth_client, prefixo):
        UFPAFactory()

        resposta = auth_client.get(prefixo)

        assert resposta.status_code == 200
        assert resposta.data == auth_client.get(CANONICA).data
        assert resposta["Deprecation"] == "true"
        assert resposta["Link"] == f'<{CANONICA}>; rel="successor-version"'

    @pytest.mark.parametrize("prefixo", [CANONICA, *ALIASES])
    @pytest.mark.parametrize("sufixo", ["membros/", "documentos/", "producao/", "formularios/", "historico/"])
    def test_rotas_aninhadas_existem_nos_tres_prefixos(self, auth_client, prefixo, sufixo):
        ufpa = UFPAFactory()

        assert auth_client.get(f"{prefixo}{ufpa.pk}/{sufixo}").status_code != 404

    @pytest.mark.parametrize("sufixo", ["exportar/", "mapa/"])
    def test_acoes_da_lista_nao_viram_detalhe(self, auth_client, sufixo):
        assert auth_client.get(f"{CANONICA}{sufixo}").status_code != 404

    def test_alias_tambem_escreve(self, auth_client_super_admin):
        ufpa = UFPAFactory()

        resposta = auth_client_super_admin.delete(f"/api/v1/upfs/{ufpa.pk}/")

        assert resposta.status_code == 204
        assert resposta["Deprecation"] == "true"

    def test_reverse_so_resolve_a_rota_canonica(self):
        ufpa_pk = 7

        assert reverse("ufpa-list") == CANONICA
        assert reverse("ufpa-detail", args=[ufpa_pk]) == f"{CANONICA}{ufpa_pk}/"
        assert reverse("ufpa-membros-list", args=[ufpa_pk]) == f"{CANONICA}{ufpa_pk}/membros/"

    def test_resposta_usa_os_nomes_novos(self, auth_client):
        ufpa = UFPAFactory()
        membro = MembroFactory(ufpa=ufpa)

        dados = auth_client.get(f"{CANONICA}{ufpa.pk}/membros/{membro.pk}/").json()

        assert dados["ufpa"] == ufpa.pk
        assert "upf" not in dados


class TestDadosComONomeAntigo:
    def test_historico_le_a_auditoria_gravada_como_upf(self, auth_client):
        ufpa = UFPAFactory()
        AuditLogFactory(
            entidade="UPF", entidade_id=str(ufpa.pk), acao="UPDATE",
            valores_anteriores={"num_comodos": 1}, valores_novos={"num_comodos": 2},
        )

        resposta = auth_client.get(f"{CANONICA}{ufpa.pk}/historico/")

        assert resposta.status_code == 200
        assert resposta.data["results"]

    def test_historico_nao_mistura_auditoria_de_outra_ufpa(self, auth_client):
        ufpa, outra = UFPAFactory(), UFPAFactory()
        AuditLogFactory(entidade="UPF", entidade_id=str(outra.pk), acao="UPDATE")

        assert auth_client.get(f"{CANONICA}{ufpa.pk}/historico/").data["results"] == []

    def test_migration_troca_o_tipo_das_exportacoes_nos_dois_sentidos(self, usuario):
        job = ExportJob.objects.create(tipo="upfs", formato="csv", solicitante=usuario)
        outro = ExportJob.objects.create(tipo="atividades", formato="csv", solicitante=usuario)

        migration_sgp.tipo_novo_das_exportacoes(apps, None)
        job.refresh_from_db()
        assert job.tipo == "ufpas"

        migration_sgp.tipo_antigo_das_exportacoes(apps, None)
        job.refresh_from_db()
        outro.refresh_from_db()
        assert (job.tipo, outro.tipo) == ("upfs", "atividades")

    def test_migration_troca_a_entidade_dos_conflitos_nos_dois_sentidos(self):
        conflito = ConflictLogFactory(entidade="upf")
        outro = ConflictLogFactory(entidade="member")

        migration_sca.entidade_nova(apps, None)
        conflito.refresh_from_db()
        assert conflito.entidade == "ufpa"

        migration_sca.entidade_antiga(apps, None)
        conflito.refresh_from_db()
        assert conflito.entidade == "upf"
        assert ConflictLog.objects.get(pk=outro.pk).entidade == "member"
