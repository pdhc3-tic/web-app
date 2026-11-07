"""Valor total da Ação: a escrita respeita o limite monetário, e a leitura nunca cai por causa dele."""
from decimal import Decimal

import pytest

from apps.sgp.models import WorkPlanAcao
from apps.sgp.tests.factories import WorkPlanAcaoFactory, WorkPlanMetaFactory, WorkPlanSubmetaFactory

pytestmark = pytest.mark.django_db

MAIOR_VALOR = "999999999999.99"
URL = "/api/v1/acoes/"


def _acao_acima_do_limite(**campos):
    return WorkPlanAcaoFactory(quantidade_planejada=2, valor_unitario=Decimal(MAIOR_VALOR), **campos)


class TestEscrita:
    def test_valor_unitario_cujo_total_nao_cabe_e_400(self, auth_client_super_admin):
        acao = WorkPlanAcaoFactory(quantidade_planejada=2, valor_unitario=100)

        resposta = auth_client_super_admin.patch(f"{URL}{acao.pk}/", {"valor_unitario": MAIOR_VALOR}, format="json")

        assert resposta.status_code == 400
        assert "valor_unitario" in resposta.data
        assert WorkPlanAcao.objects.get(pk=acao.pk).valor_unitario == Decimal("100.00")

    def test_quantidade_cujo_total_nao_cabe_e_400(self, auth_client_super_admin):
        acao = WorkPlanAcaoFactory(quantidade_planejada=1, valor_unitario=Decimal(MAIOR_VALOR))

        resposta = auth_client_super_admin.patch(f"{URL}{acao.pk}/", {"quantidade_planejada": 2}, format="json")

        assert resposta.status_code == 400

    def test_maior_total_que_cabe_e_aceito(self, auth_client_super_admin):
        acao = WorkPlanAcaoFactory(quantidade_planejada=1, valor_unitario=100)

        resposta = auth_client_super_admin.patch(f"{URL}{acao.pk}/", {"valor_unitario": MAIOR_VALOR}, format="json")

        assert resposta.status_code == 200, resposta.data
        assert resposta.data["valor_total"] == MAIOR_VALOR


class TestLeitura:
    """Dados gravados por fora da API, como pelo Admin, não podem derrubar a tela de ninguém."""

    def test_detalhe_e_lista_com_total_acima_do_limite(self, auth_client_super_admin):
        acao = _acao_acima_do_limite()

        assert auth_client_super_admin.get(f"{URL}{acao.pk}/").data["valor_total"] == "1999999999999.98"
        assert auth_client_super_admin.get(URL).status_code == 200

    def test_soma_na_submeta_e_na_meta_acima_do_limite(self, auth_client_super_admin):
        meta = WorkPlanMetaFactory()
        submeta = WorkPlanSubmetaFactory(meta=meta)
        _acao_acima_do_limite(meta=meta, submeta=submeta)
        _acao_acima_do_limite(meta=meta, submeta=submeta)

        assert auth_client_super_admin.get(f"/api/v1/sgp/submetas/{submeta.pk}/").status_code == 200
        assert auth_client_super_admin.get(f"/api/v1/metas/{meta.pk}/").status_code == 200
        assert auth_client_super_admin.get("/api/v1/sgp/plano-trabalho/painel/").status_code == 200
