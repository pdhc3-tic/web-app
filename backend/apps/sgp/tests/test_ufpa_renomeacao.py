"""Renomeação de UPF para UFPA: rotas antigas por um ciclo e dados gravados com o nome antigo."""
import importlib

import pytest
from django.apps import apps
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from apps.core.tests.factories import AuditLogFactory, MunicipalityFactory, TerritoryFactory
from apps.sca.models import ConflictLog
from apps.sca.tests.factories import ConflictLogFactory
from apps.sgp.models import UFPA, ExportJob
from apps.sgp.tests.factories import ActivityFactory, MembroFactory, UFPAFactory

pytestmark = pytest.mark.django_db

CANONICA = "/api/v1/sgp/ufpas/"
ALIASES = ["/api/v1/upfs/", "/api/v1/sgp/upfs/"]

migration_sgp = importlib.import_module("apps.sgp.migrations.0021_renomeia_upf_para_ufpa")
migration_sca = importlib.import_module("apps.sca.migrations.0007_conflitos_com_a_entidade_ufpa")


def _ufpa():
    return UFPAFactory(municipio=MunicipalityFactory(territory=TerritoryFactory()))


class TestRotas:
    def test_canonica_responde_sem_aviso_de_depreciacao(self, auth_client):
        _ufpa()

        resposta = auth_client.get(CANONICA)

        assert resposta.status_code == 200
        assert resposta.data["count"] == 1
        assert "Deprecation" not in resposta

    @pytest.mark.parametrize("prefixo", ALIASES)
    def test_alias_responde_o_mesmo_e_avisa_a_depreciacao(self, auth_client, prefixo):
        _ufpa()

        resposta = auth_client.get(prefixo)

        assert resposta.status_code == 200
        assert resposta.data == auth_client.get(CANONICA).data
        assert resposta["Deprecation"] == "true"
        assert resposta["Link"] == f'<{CANONICA}>; rel="successor-version"'

    @pytest.mark.parametrize("prefixo", ALIASES)
    @pytest.mark.parametrize("sufixo", ["membros/", "documentos/", "producao/", "formularios/", "historico/"])
    def test_rotas_aninhadas_existem_nos_tres_prefixos(self, auth_client, prefixo, sufixo):
        ufpa = _ufpa()

        assert auth_client.get(f"{CANONICA}{ufpa.pk}/{sufixo}").status_code == 200
        assert auth_client.get(f"{prefixo}{ufpa.pk}/{sufixo}").status_code == 200

    @pytest.mark.parametrize("prefixo", ALIASES)
    def test_link_do_alias_aponta_para_a_mesma_rota_aninhada(self, auth_client, prefixo):
        ufpa = _ufpa()

        resposta = auth_client.get(f"{prefixo}{ufpa.pk}/membros/")

        assert resposta["Link"] == f'<{CANONICA}{ufpa.pk}/membros/>; rel="successor-version"'

    @pytest.mark.parametrize("prefixo", [CANONICA, *ALIASES])
    @pytest.mark.parametrize("sufixo", ["exportar/", "mapa/"])
    def test_acoes_da_lista_nao_viram_detalhe(self, auth_client_super_admin, prefixo, sufixo):
        _ufpa()

        assert auth_client_super_admin.get(f"{prefixo}{sufixo}").status_code == 200

    @pytest.mark.parametrize("prefixo", ALIASES)
    def test_alias_tambem_escreve(self, auth_client_super_admin, prefixo):
        ufpa = _ufpa()

        resposta = auth_client_super_admin.delete(f"{prefixo}{ufpa.pk}/")

        assert resposta.status_code == 204
        assert resposta["Deprecation"] == "true"

    def test_reverse_so_resolve_a_rota_canonica(self):
        ufpa_pk = 7

        assert reverse("ufpa-list") == CANONICA
        assert reverse("ufpa-detail", args=[ufpa_pk]) == f"{CANONICA}{ufpa_pk}/"
        assert reverse("ufpa-membros-list", args=[ufpa_pk]) == f"{CANONICA}{ufpa_pk}/membros/"

    def test_resposta_usa_os_nomes_novos(self, auth_client):
        ufpa = _ufpa()
        membro = MembroFactory(ufpa=ufpa)

        dados = auth_client.get(f"{CANONICA}{ufpa.pk}/membros/{membro.pk}/").json()

        assert dados["ufpa"] == ufpa.pk
        assert "upf" not in dados


class TestDadosComONomeAntigo:
    def test_historico_le_a_auditoria_gravada_como_upf(self, auth_client):
        ufpa = _ufpa()
        AuditLogFactory(
            entidade="UPF", entidade_id=str(ufpa.pk), acao="UPF.update",
            valores_anteriores={"num_comodos": 1}, valores_novos={"num_comodos": 2},
        )

        resposta = auth_client.get(f"{CANONICA}{ufpa.pk}/historico/")

        assert resposta.status_code == 200
        entrada = resposta.data["results"][0]
        assert (entrada["campo"], entrada["valor_anterior"], entrada["valor_novo"]) == ("num_comodos", 1, 2)

    def test_historico_nao_mistura_auditoria_de_outra_ufpa(self, auth_client):
        ufpa, outra = _ufpa(), _ufpa()
        AuditLogFactory(entidade="UPF", entidade_id=str(outra.pk), acao="UPF.update")

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

    def test_filtro_da_auditoria_traz_as_linhas_com_o_nome_antigo(self, auth_client_super_admin):
        antiga = AuditLogFactory(entidade="UPF", acao="UPF.update")
        nova = AuditLogFactory(entidade="UFPA", acao="UFPA.update")
        AuditLogFactory(entidade="MembroFamilia", acao="MembroFamilia.update")

        resposta = auth_client_super_admin.get("/api/v1/audit-logs/", {"entidade": "UFPA"})

        assert {item["id"] for item in resposta.data["results"]} == {antiga.pk, nova.pk}

    def test_filtro_da_auditoria_de_outra_entidade_continua_exato(self, auth_client_super_admin):
        AuditLogFactory(entidade="UPF", acao="UPF.update")
        membro = AuditLogFactory(entidade="MembroFamilia", acao="MembroFamilia.update")

        resposta = auth_client_super_admin.get("/api/v1/audit-logs/", {"entidade": "MembroFamilia"})

        assert [item["id"] for item in resposta.data["results"]] == [membro.pk]

    def test_migration_troca_entidade_e_campo_dos_conflitos_nos_dois_sentidos(self):
        da_ufpa = ConflictLogFactory(entidade="upf", campo="whatsapp")
        do_membro = ConflictLogFactory(entidade="member", campo="upf")
        da_atividade = ConflictLogFactory(entidade="activity", campo="upfs_participantes")
        sem_mudanca = ConflictLogFactory(entidade="member", campo="whatsapp")

        migration_sca.nomes_novos(apps, None)

        assert ConflictLog.objects.get(pk=da_ufpa.pk).entidade == "ufpa"
        assert ConflictLog.objects.get(pk=do_membro.pk).campo == "ufpa"
        assert ConflictLog.objects.get(pk=da_atividade.pk).campo == "ufpas_participantes"

        migration_sca.nomes_antigos(apps, None)

        assert ConflictLog.objects.get(pk=da_ufpa.pk).entidade == "upf"
        assert ConflictLog.objects.get(pk=do_membro.pk).campo == "upf"
        assert ConflictLog.objects.get(pk=da_atividade.pk).campo == "upfs_participantes"
        assert (sem_mudanca.entidade, ConflictLog.objects.get(pk=sem_mudanca.pk).campo) == ("member", "whatsapp")


    def test_migration_renomeia_as_permissoes_sem_perder_quem_as_tinha(self, usuario):
        tipo = ContentType.objects.get_for_model(UFPA)
        Permission.objects.filter(content_type=tipo, codename="change_ufpa").delete()
        antiga = Permission.objects.create(content_type=tipo, codename="change_upf", name="Can change UPF")
        usuario.user_permissions.add(antiga)

        migration_sgp.permissoes_novas(apps, None)

        antiga.refresh_from_db()
        assert (antiga.codename, antiga.name) == ("change_ufpa", "Can change UFPA")
        assert usuario.user_permissions.filter(pk=antiga.pk).exists()

        migration_sgp.permissoes_antigas(apps, None)

        antiga.refresh_from_db()
        assert (antiga.codename, antiga.name) == ("change_upf", "Can change UPF")

    def test_migration_nao_duplica_permissao_que_ja_existe_com_o_nome_novo(self):
        tipo = ContentType.objects.get_for_model(UFPA)
        nova, _ = Permission.objects.get_or_create(
            content_type=tipo, codename="view_ufpa", defaults={"name": "Can view UFPA"},
        )
        antiga = Permission.objects.create(content_type=tipo, codename="view_upf", name="Can view UPF")

        migration_sgp.permissoes_novas(apps, None)

        antiga.refresh_from_db()
        assert antiga.codename == "view_upf"
        assert Permission.objects.filter(content_type=tipo, codename="view_ufpa").get().pk == nova.pk


class TestNomesAntigosNaEscrita:
    def test_atividade_recusa_a_chave_antiga_de_participantes(self, auth_client_super_admin):
        atividade = ActivityFactory()

        resposta = auth_client_super_admin.patch(
            f"/api/v1/sgp/atividades/{atividade.pk}/", {"upfs_participantes": []}, format="json",
        )

        assert resposta.status_code == 400
        assert "ufpas_participantes" in str(resposta.data["upfs_participantes"])

    def test_atividade_aceita_a_chave_nova(self, auth_client_super_admin):
        atividade, ufpa = ActivityFactory(), _ufpa()

        resposta = auth_client_super_admin.patch(
            f"/api/v1/sgp/atividades/{atividade.pk}/", {"ufpas_participantes": [ufpa.pk]}, format="json",
        )

        assert resposta.status_code == 200, resposta.data
        assert list(atividade.ufpas_participantes.values_list("pk", flat=True)) == [ufpa.pk]

    def test_ufpa_recusa_daf_caf(self, auth_client_super_admin):
        ufpa = _ufpa()

        resposta = auth_client_super_admin.patch(f"{CANONICA}{ufpa.pk}/", {"daf_caf": "123"}, format="json")

        assert resposta.status_code == 400
        assert "dap_caf" in str(resposta.data["daf_caf"])

    def test_ufpa_grava_e_devolve_dap_caf(self, auth_client_super_admin):
        ufpa = _ufpa()

        resposta = auth_client_super_admin.patch(f"{CANONICA}{ufpa.pk}/", {"dap_caf": "123"}, format="json")

        assert resposta.status_code == 200, resposta.data
        assert resposta.data["dap_caf"] == "123"
        ufpa.refresh_from_db()
        assert ufpa.numero_dap == "123"
