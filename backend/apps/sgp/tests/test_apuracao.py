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


@pytest.fixture
def nova_upf(municipio_rn):
    """UFPA com território: a UPFFactory sozinha cria município sem território."""
    return lambda: UPFFactory(municipio=municipio_rn)


@pytest.fixture
def novo_membro(nova_upf):
    return lambda: MembroFactory(upf=nova_upf())


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
    def test_ufpa_em_varias_atividades_conta_uma_vez(self, nova_upf):
        acao = _acao("soma_ufpas")
        repetida, outra = nova_upf(), nova_upf()
        primeira = ActivityFactory(acao=acao, status="concluido")
        segunda = ActivityFactory(acao=acao, status="concluido")
        primeira.upfs_participantes.add(repetida, outra)
        segunda.upfs_participantes.add(repetida)

        assert _realizado(acao) == 2

    def test_so_atividades_concluidas_contam(self, nova_upf):
        acao = _acao("soma_ufpas")
        pendente = ActivityFactory(acao=acao, status="em_andamento")
        pendente.upfs_participantes.add(nova_upf())

        assert _realizado(acao) == 0

        pendente.status = "concluido"
        pendente.save()
        assert _realizado(acao) == 1

    def test_remover_e_limpar_vinculos_pela_atividade(self, nova_upf):
        acao = _acao("soma_ufpas")
        upf_a, upf_b = nova_upf(), nova_upf()
        atividade = ActivityFactory(acao=acao, status="concluido")
        atividade.upfs_participantes.add(upf_a, upf_b)

        atividade.upfs_participantes.remove(upf_a)
        assert _realizado(acao) == 1

        atividade.upfs_participantes.clear()
        assert _realizado(acao) == 0

    def test_alterar_vinculos_pelo_lado_da_ufpa(self, nova_upf):
        acao = _acao("soma_ufpas")
        upf = nova_upf()
        atividade = ActivityFactory(acao=acao, status="concluido")

        upf.atividades.add(atividade)
        assert _realizado(acao) == 1

        upf.atividades.clear()
        assert _realizado(acao) == 0


class TestSomaDeParticipantes:
    def test_membro_em_varias_atividades_conta_uma_vez(self, novo_membro):
        acao = _acao("soma_participantes")
        membro, outro = novo_membro(), novo_membro()
        primeira = ActivityFactory(acao=acao, status="concluido")
        segunda = ActivityFactory(acao=acao, status="concluido")
        primeira.membros_participantes.add(membro, outro)
        segunda.membros_participantes.add(membro)

        assert _realizado(acao) == 2

    def test_remover_pelo_lado_do_membro(self, novo_membro):
        acao = _acao("soma_participantes")
        membro = novo_membro()
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
        assert response.data["quantidade_realizada"] == "12.00"
        assert _realizado(acao) == 12

    def test_lancamento_manual_precisa_ser_inteiro(self, auth_client):
        acao = _acao("manual")

        response = auth_client.patch(
            f"/api/v1/acoes/{acao.pk}/", {"quantidade_realizada": "2.50"}, format="json"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_lancamento_manual_recusado_nas_outras_formas(self, auth_client):
        acao = _acao("soma_ufpas")

        response = auth_client.patch(
            f"/api/v1/acoes/{acao.pk}/", {"quantidade_realizada": 12}, format="json"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "quantidade_realizada" in response.data

    def test_devolver_o_valor_apurado_nas_outras_formas_e_tolerado(self, auth_client):
        acao = _acao("soma_ufpas")

        response = auth_client.patch(
            f"/api/v1/acoes/{acao.pk}/",
            {"quantidade_realizada": acao.quantidade_realizada, "descricao": "Nova"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK, response.data
        assert _realizado(acao) == acao.quantidade_realizada


class TestTrocaDeIndicadorDaAcao:
    def test_reapura_pela_forma_do_novo_indicador(self, auth_client, nova_upf):
        acao = _acao("contagem_atividades")
        upf = nova_upf()
        for _ in range(3):
            ActivityFactory(acao=acao, status="concluido").upfs_participantes.add(upf)
        assert _realizado(acao) == 3

        response = auth_client.patch(
            f"/api/v1/acoes/{acao.pk}/",
            {"indicador": IndicatorFactory(forma_apuracao="soma_ufpas").pk},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK, response.data
        assert response.data["quantidade_realizada"] == "1.00"
        assert _realizado(acao) == 1

    def test_sair_da_forma_manual_descarta_o_lancamento(self, auth_client):
        acao = _acao("manual", quantidade_realizada=40)
        ActivityFactory(acao=acao, status="concluido")

        auth_client.patch(
            f"/api/v1/acoes/{acao.pk}/",
            {"indicador": IndicatorFactory(forma_apuracao="contagem_atividades").pk},
            format="json",
        )

        assert _realizado(acao) == 1


class TestTrocaDeIndicadorForaDaApi:
    def test_salvar_a_acao_com_outro_indicador_reapura(self, nova_upf):
        acao = _acao("contagem_atividades")
        ActivityFactory(acao=acao, status="concluido").upfs_participantes.add(nova_upf(), nova_upf())
        assert _realizado(acao) == 1

        acao.indicador = IndicatorFactory(forma_apuracao="soma_ufpas")
        acao.save()

        assert _realizado(acao) == 2


class TestExclusaoDeParticipantes:
    def test_excluir_membro_reapura(self, novo_membro):
        acao = _acao("soma_participantes")
        membro, outro = novo_membro(), novo_membro()
        atividade = ActivityFactory(acao=acao, status="concluido")
        atividade.membros_participantes.add(membro, outro)
        assert _realizado(acao) == 2

        membro.delete()

        assert _realizado(acao) == 1


class TestReconciliacao:
    def test_check_only_detecta_e_correcao_ajusta(self, nova_upf):
        acao = _acao("soma_ufpas")
        atividade = ActivityFactory(acao=acao, status="concluido")
        atividade.upfs_participantes.add(nova_upf(), nova_upf())
        WorkPlanAcao.objects.filter(pk=acao.pk).update(quantidade_realizada=9)

        with pytest.raises(CommandError, match="apuração dá 2"):
            call_command("verificar_progresso_acoes", "--check-only")
        assert _realizado(acao) == 9

        call_command("verificar_progresso_acoes")
        assert _realizado(acao) == 2

    def test_acoes_manuais_ficam_de_fora(self):
        _acao("manual", quantidade_realizada=5)

        call_command("verificar_progresso_acoes", "--check-only")
