"""Quantidade realizada conforme a forma de apuração do Indicador (SGP §5.4, RF21)."""
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from rest_framework import status

from apps.sgp.models import WorkPlanAcao
from apps.sgp.tests.factories import (
    ActivityFactory,
    IndicatorFactory,
    MembroFactory,
    UPFFactory,
    WorkPlanAcaoFactory,
)

pytestmark = pytest.mark.django_db


def _acao(forma, **kwargs):
    return WorkPlanAcaoFactory(indicador=IndicatorFactory(forma_apuracao=forma), **kwargs)


def _realizado(acao):
    acao.refresh_from_db(fields=["quantidade_realizada"])
    return acao.quantidade_realizada


class TestContagemDeAtividades:
    def test_conta_so_concluidas_e_ativas(self):
        acao = _acao("contagem_atividades")
        ActivityFactory(acao=acao, status="concluido")
        ActivityFactory(acao=acao, status="concluido")
        ActivityFactory(acao=acao, status="em_andamento")
        removida = ActivityFactory(acao=acao, status="concluido")

        assert _realizado(acao) == 3

        removida.soft_delete()
        assert _realizado(acao) == 2

    def test_sair_de_concluido_desconta(self):
        acao = _acao("contagem_atividades")
        atividade = ActivityFactory(acao=acao, status="concluido")
        atividade.status = "cancelada"
        atividade.save()

        assert _realizado(acao) == 0

    def test_trocar_de_acao_recalcula_as_duas(self):
        origem = _acao("contagem_atividades")
        destino = _acao("contagem_atividades")
        atividade = ActivityFactory(acao=origem, status="concluido")

        atividade.acao = destino
        atividade.save()

        assert _realizado(origem) == 0
        assert _realizado(destino) == 1


class TestSomaDeUfpas:
    def test_ufpa_em_varias_atividades_conta_uma_vez(self):
        acao = _acao("soma_ufpas")
        repetida, outra = UPFFactory(), UPFFactory()
        primeira = ActivityFactory(acao=acao, status="concluido")
        segunda = ActivityFactory(acao=acao, status="concluido")
        primeira.upfs_participantes.add(repetida, outra)
        segunda.upfs_participantes.add(repetida)

        assert _realizado(acao) == 2

    def test_so_atividades_concluidas_contam(self):
        acao = _acao("soma_ufpas")
        pendente = ActivityFactory(acao=acao, status="em_andamento")
        pendente.upfs_participantes.add(UPFFactory())

        assert _realizado(acao) == 0

        pendente.status = "concluido"
        pendente.save()
        assert _realizado(acao) == 1

    def test_remover_e_limpar_vinculos_pela_atividade(self):
        acao = _acao("soma_ufpas")
        upf_a, upf_b = UPFFactory(), UPFFactory()
        atividade = ActivityFactory(acao=acao, status="concluido")
        atividade.upfs_participantes.add(upf_a, upf_b)

        atividade.upfs_participantes.remove(upf_a)
        assert _realizado(acao) == 1

        atividade.upfs_participantes.clear()
        assert _realizado(acao) == 0

    def test_alterar_vinculos_pelo_lado_da_ufpa(self):
        acao = _acao("soma_ufpas")
        upf = UPFFactory()
        atividade = ActivityFactory(acao=acao, status="concluido")

        upf.atividades.add(atividade)
        assert _realizado(acao) == 1

        upf.atividades.clear()
        assert _realizado(acao) == 0


class TestSomaDeParticipantes:
    def test_membro_em_varias_atividades_conta_uma_vez(self):
        acao = _acao("soma_participantes")
        membro, outro = MembroFactory(), MembroFactory()
        primeira = ActivityFactory(acao=acao, status="concluido")
        segunda = ActivityFactory(acao=acao, status="concluido")
        primeira.membros_participantes.add(membro, outro)
        segunda.membros_participantes.add(membro)

        assert _realizado(acao) == 2

    def test_remover_pelo_lado_do_membro(self):
        acao = _acao("soma_participantes")
        membro = MembroFactory()
        atividade = ActivityFactory(acao=acao, status="concluido")
        atividade.membros_participantes.add(membro)

        membro.atividades.remove(atividade)

        assert _realizado(acao) == 0


class TestManual:
    def test_atividades_nao_alteram_o_valor_lancado(self):
        acao = _acao("manual", quantidade_realizada=7)
        ActivityFactory(acao=acao, status="concluido")

        assert _realizado(acao) == 7

    def test_ugp_lanca_pela_api(self, auth_client):
        acao = _acao("manual")

        response = auth_client.patch(
            f"/api/v1/acoes/{acao.pk}/", {"quantidade_realizada": 12}, format="json"
        )

        assert response.status_code == status.HTTP_200_OK, response.data
        assert _realizado(acao) == 12

    def test_lancamento_manual_recusado_nas_outras_formas(self, auth_client):
        acao = _acao("soma_ufpas")

        response = auth_client.patch(
            f"/api/v1/acoes/{acao.pk}/", {"quantidade_realizada": 12}, format="json"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "quantidade_realizada" in response.data


class TestReconciliacao:
    def test_check_only_detecta_e_correcao_ajusta(self):
        acao = _acao("soma_ufpas")
        atividade = ActivityFactory(acao=acao, status="concluido")
        atividade.upfs_participantes.add(UPFFactory(), UPFFactory())
        WorkPlanAcao.objects.filter(pk=acao.pk).update(quantidade_realizada=9)

        with pytest.raises(CommandError, match="apuração dá 2"):
            call_command("verificar_progresso_acoes", "--check-only")
        assert _realizado(acao) == 9

        call_command("verificar_progresso_acoes")
        assert _realizado(acao) == 2

    def test_acoes_manuais_ficam_de_fora(self):
        _acao("manual", quantidade_realizada=5)

        call_command("verificar_progresso_acoes", "--check-only")
