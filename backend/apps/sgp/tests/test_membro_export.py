"""
Issue #186 — Endpoint de exportação de membros (CSV).

Cobre: export por UFPA específica, export territorial agregado, filtragem de
colunas sensíveis (reaproveitando a matriz da Issue #187) e limite de UFPAs
por exportação agregada.
"""
import csv
import io

import pytest

from apps.sgp.tests.factories import MembroFactory

pytestmark = pytest.mark.django_db


def _parse_csv(response):
    content = response.content.decode("utf-8-sig")
    return list(csv.reader(io.StringIO(content)))


class TestExportarMembrosPorUfpa:
    def test_exporta_todos_os_membros_esperados_da_ufpa(self, auth_client_adt_rn, ufpa):
        MembroFactory(ufpa=ufpa, grau_parentesco="filho", nome_completo="Filho Um")
        MembroFactory(ufpa=ufpa, grau_parentesco="filho", nome_completo="Filho Dois")

        response = auth_client_adt_rn.get(f"/api/v1/sgp/ufpas/{ufpa.pk}/membros/exportar/")
        assert response.status_code == 200
        assert response["Content-Type"] == "text/csv; charset=utf-8"
        assert "attachment;" in response["Content-Disposition"]

        rows = _parse_csv(response)
        header, *data = rows
        nomes = {row[header.index("Nome completo")] for row in data}
        # ufpa.titular (criado pela UFPAFactory) + os dois membros criados aqui.
        assert {"Filho Um", "Filho Dois", ufpa.titular.nome_completo}.issubset(nomes)

    def test_usuario_sem_permissao_de_saude_recebe_csv_sem_a_coluna(
        self, auth_client_adt_rn, ufpa, monkeypatch
    ):
        from apps.core import sensitive_fields as sf

        monkeypatch.setitem(sf.SENSITIVE_FIELD_ROLES, "saude", {"super-admin"})
        MembroFactory(ufpa=ufpa, grau_parentesco="filho", saude=["diabetes"])

        response = auth_client_adt_rn.get(f"/api/v1/sgp/ufpas/{ufpa.pk}/membros/exportar/")
        header = _parse_csv(response)[0]
        assert "Condições de saúde" not in header
        assert "Cor/Raça" in header  # adt-acr continua vendo cor_raca

    def test_ufpa_fora_do_escopo_retorna_404(self, auth_client_adt_rn, ufpa_ce):
        response = auth_client_adt_rn.get(f"/api/v1/sgp/ufpas/{ufpa_ce.pk}/membros/exportar/")
        assert response.status_code == 404


class TestExportarMembrosAgregado:
    def test_export_territorial_nao_inclui_membros_fora_do_escopo(
        self, auth_client_adt_rn, ufpa, ufpa_ce
    ):
        """adt_rn está restrito a territory_rn; ufpa_ce vive em territory_ce."""
        MembroFactory(ufpa=ufpa, grau_parentesco="filho", nome_completo="Dentro do Escopo")
        MembroFactory(ufpa=ufpa_ce, grau_parentesco="filho", nome_completo="Fora do Escopo")

        response = auth_client_adt_rn.get("/api/v1/sgp/membros/exportar/")
        assert response.status_code == 200
        rows = _parse_csv(response)
        header, *data = rows
        nomes = {row[header.index("Nome completo")] for row in data}
        assert "Dentro do Escopo" in nomes
        assert "Fora do Escopo" not in nomes

    def test_filtro_por_territorio_id(self, auth_client_super_admin, ufpa, ufpa_ce):
        MembroFactory(ufpa=ufpa, grau_parentesco="filho", nome_completo="Membro RN")
        MembroFactory(ufpa=ufpa_ce, grau_parentesco="filho", nome_completo="Membro CE")

        response = auth_client_super_admin.get(
            f"/api/v1/sgp/membros/exportar/?territorio_id={ufpa.territorio_id}"
        )
        header, *data = _parse_csv(response)
        nomes = {row[header.index("Nome completo")] for row in data}
        assert "Membro RN" in nomes
        assert "Membro CE" not in nomes

    def test_filtro_por_municipio_e_projeto(self, auth_client_super_admin, ufpa):
        MembroFactory(ufpa=ufpa, grau_parentesco="filho", nome_completo="Membro Filtrado")

        response = auth_client_super_admin.get(
            "/api/v1/sgp/membros/exportar/"
            f"?municipio={ufpa.municipio_id}&projeto={ufpa.projeto_id}"
        )
        assert response.status_code == 200
        header, *data = _parse_csv(response)
        nomes = {row[header.index("Nome completo")] for row in data}
        assert "Membro Filtrado" in nomes

    def test_filtro_invalido_retorna_400(self, auth_client_super_admin):
        response = auth_client_super_admin.get("/api/v1/sgp/membros/exportar/?territorio_id=abc")
        assert response.status_code == 400

    def test_excede_limite_de_ufpas_retorna_400_com_mensagem_clara(
        self, auth_client_super_admin, ufpa, monkeypatch
    ):
        from apps.sgp.services import membro_export as membro_export_service

        monkeypatch.setattr(membro_export_service, "MEMBROS_EXPORT_UFPA_LIMIT", 0)

        response = auth_client_super_admin.get("/api/v1/sgp/membros/exportar/")
        assert response.status_code == 400
        assert "limite" in response.data["detail"].lower()

    def test_usuario_sem_acesso_a_ufpas_recebe_csv_vazio_sem_erro(self, auth_client_fgd):
        """fgd não tem UFPAs no escopo — resposta é um CSV válido, só com cabeçalho."""
        response = auth_client_fgd.get("/api/v1/sgp/membros/exportar/")
        assert response.status_code == 200
        rows = _parse_csv(response)
        assert len(rows) == 1  # só o cabeçalho
