"""Rota de riscos de glosa: filtros, ordem e recorte por perfil."""
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from freezegun import freeze_time

from apps.sgd.tests.factories import ApprovalStepFactory, DemandFactory
from apps.sgp.models import GlosaRisk
from apps.sgp.tests.factories import ActivityFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/sgp/glosa-riscos/"
Tipo = GlosaRisk.Tipo
Severidade = GlosaRisk.Severidade


def _risco(demanda_id=1, *, tipo=Tipo.PAGO_ACIMA_AUTORIZADO, severidade=Severidade.ALTA, activity=None,
           exposto="100.00", solicitacao=None):
    if solicitacao is None:
        solicitacao = str(demanda_id) if tipo == Tipo.PAGO_ACIMA_AUTORIZADO else ""
    return GlosaRisk.objects.create(
        tipo_situacao=tipo, severidade=severidade, entidade=GlosaRisk.ENTIDADE_DEMANDA,
        entidade_id=str(demanda_id), activity=activity, demanda_id=str(demanda_id),
        demand_request_id=solicitacao, valor_exposto=Decimal(exposto),
    )


def _demanda(activity, estado_sigla, territorio, *, status="concluida"):
    """O estado e o território da demanda são os do solicitante, não os da atividade."""
    return DemandFactory(activity=activity, estado_sigla=estado_sigla, territorio=territorio, status=status)


def _ids(resposta):
    assert resposta.status_code == 200, resposta.data
    return [item["id"] for item in resposta.data["results"]]


@pytest.fixture
def atividade_rn(municipio_rn):
    return ActivityFactory(municipio=municipio_rn)


@pytest.fixture
def atividade_ce(municipio_ce):
    return ActivityFactory(municipio=municipio_ce)


class TestResposta:
    @freeze_time("2026-11-01 13:30:00")
    def test_traz_o_formato_combinado_com_ids_inteiros(self, auth_client, atividade_rn):
        risco = GlosaRisk.objects.create(
            tipo_situacao=Tipo.PAGO_ACIMA_AUTORIZADO, severidade=Severidade.ALTA,
            entidade=GlosaRisk.ENTIDADE_DEMANDA, entidade_id="70800", activity=atividade_rn,
            demanda_id="70800", demand_request_id="42", valor_autorizado=Decimal("1200.00"),
            valor_pago=Decimal("1400.00"), valor_exposto=Decimal("200.00"),
        )

        item = auth_client.get(URL).json()["results"][0]

        assert item == {
            "id": risco.pk,
            "tipo": "pago_acima_autorizado",
            "severidade": "alta",
            "valor_exposto": "200.00",
            "activity_id": atividade_rn.pk,
            "demanda_id": 70800,
            "demand_request_id": 42,
            "valor_autorizado": "1200.00",
            "valor_pago": "1400.00",
            "criado_em": item["criado_em"],
            "resolvido_em": None,
        }
        assert item["criado_em"].startswith("2026-11-01")

    def test_risco_sem_evidencia_vem_sem_solicitacao_nem_valores_do_pagamento(self, auth_client):
        _risco(7, tipo=Tipo.DEMANDA_SEM_EVIDENCIA)

        item = auth_client.get(URL).json()["results"][0]

        assert (item["demand_request_id"], item["valor_autorizado"], item["valor_pago"]) == (None, None, None)

    def test_rota_e_somente_leitura(self, auth_client):
        assert auth_client.post(URL, {}, format="json").status_code == 405


class TestFiltrosEOrdem:
    def test_sem_filtro_ordena_por_valor_exposto(self, auth_client):
        menor = _risco(1, exposto="50.00")
        maior = _risco(2, exposto="900.00")
        medio = _risco(3, exposto="300.00")

        assert _ids(auth_client.get(URL)) == [maior.pk, medio.pk, menor.pk]

    def test_por_atividade(self, auth_client, atividade_rn, atividade_ce):
        desta = _risco(1, activity=atividade_rn)
        _risco(2, activity=atividade_ce)

        assert _ids(auth_client.get(URL, {"activity": atividade_rn.pk})) == [desta.pk]

    def test_por_tipo(self, auth_client):
        sem_evidencia = _risco(1, tipo=Tipo.DEMANDA_SEM_EVIDENCIA)
        _risco(2)

        assert _ids(auth_client.get(URL, {"tipo": "demanda_sem_evidencia"})) == [sem_evidencia.pk]

    def test_por_severidade(self, auth_client):
        media = _risco(1, severidade=Severidade.MEDIA)
        _risco(2)

        assert _ids(auth_client.get(URL, {"severidade": "media"})) == [media.pk]

    def test_por_demanda_em_ordem_cronologica(self, auth_client):
        with freeze_time("2026-11-02 10:00"):
            segundo = _risco(70, exposto="900.00", solicitacao="2")
        with freeze_time("2026-11-01 10:00"):
            primeiro = _risco(70, exposto="10.00", solicitacao="1")
        _risco(71)

        assert _ids(auth_client.get(URL, {"demanda": 70})) == [primeiro.pk, segundo.pk]

    def test_demanda_sem_risco_devolve_lista_vazia(self, auth_client):
        _risco(70)

        assert _ids(auth_client.get(URL, {"demanda": 71})) == []

    @pytest.mark.parametrize("parametro", [
        {"tipo": "outro"}, {"severidade": "critica"}, {"activity": "abc"}, {"demanda": "abc"},
    ])
    def test_filtro_invalido_e_400(self, auth_client, parametro):
        assert auth_client.get(URL, parametro).status_code == 400


class TestPerfis:
    @pytest.mark.parametrize("cliente", ["auth_client", "auth_client_super_admin", "auth_client_fgd"])
    def test_coordenacao_e_fgd_veem_todos(self, request, cliente, atividade_rn, atividade_ce):
        riscos = {_risco(1, activity=atividade_rn).pk, _risco(2, activity=atividade_ce).pk, _risco(3).pk}

        assert set(_ids(request.getfixturevalue(cliente).get(URL))) == riscos

    def test_articulador_ve_os_riscos_das_demandas_do_seu_estado_e_nao_o_da_atividade(
        self, auth_client_articulador_rn, atividade_rn, atividade_ce, territory_rn, territory_ce,
    ):
        do_rn_com_atividade_no_ce = _demanda(atividade_ce, "RN", territory_rn)
        do_ce_com_atividade_no_rn = _demanda(atividade_rn, "CE", territory_ce)
        nacional = _demanda(atividade_rn, None, None)
        visivel = _risco(do_rn_com_atividade_no_ce.pk, activity=atividade_ce)
        _risco(do_ce_com_atividade_no_rn.pk, activity=atividade_rn)
        _risco(nacional.pk, activity=atividade_rn)
        _risco(999_999, activity=atividade_rn)  # referência a demanda inexistente

        assert _ids(auth_client_articulador_rn.get(URL)) == [visivel.pk]

    def test_por_demanda_articulador_ve_os_riscos_da_demanda_que_esta_na_fila_dele(
        self, auth_client_articulador_rn, atividade_rn, atividade_ce, territory_rn, territory_ce,
    ):
        da_fila = _demanda(atividade_ce, "RN", territory_rn, status="submetida")
        de_outro_estado = _demanda(atividade_rn, "CE", territory_ce, status="submetida")
        risco = _risco(da_fila.pk, activity=atividade_ce)
        _risco(de_outro_estado.pk, activity=atividade_rn)

        assert _ids(auth_client_articulador_rn.get(URL, {"demanda": da_fila.pk})) == [risco.pk]
        assert _ids(auth_client_articulador_rn.get(URL, {"demanda": de_outro_estado.pk})) == []

    def test_articulador_ve_o_risco_da_demanda_que_decidiu_em_outro_estado(
        self, auth_client_articulador_rn, usuario_articulador_rn, atividade_ce, territory_ce,
    ):
        decidida = _demanda(atividade_ce, "CE", territory_ce)
        ApprovalStepFactory(demanda=decidida, responsavel=usuario_articulador_rn)
        risco = _risco(decidida.pk, activity=atividade_ce)

        assert _ids(auth_client_articulador_rn.get(URL, {"demanda": decidida.pk})) == [risco.pk]
        assert _ids(auth_client_articulador_rn.get(URL)) == [risco.pk]

    def test_articulador_continua_vendo_o_risco_de_atividade_inativa(
        self, auth_client_articulador_rn, municipio_rn, territory_rn,
    ):
        atividade = ActivityFactory(municipio=municipio_rn, ativo=False)
        risco = _risco(_demanda(atividade, "RN", territory_rn).pk, activity=atividade)

        assert _ids(auth_client_articulador_rn.get(URL)) == [risco.pk]

    @pytest.mark.parametrize("cliente", ["auth_client_adt_rn", "auth_client_sem_acesso"])
    def test_demais_perfis_recebem_403(self, request, cliente, atividade_rn):
        _risco(1, activity=atividade_rn)

        assert request.getfixturevalue(cliente).get(URL).status_code == 403

    def test_sem_login_recebe_401(self, api_client):
        assert api_client.get(URL).status_code == 401


class TestUnicidade:
    def test_duas_demandas_sem_evidencia_nao_colidem(self):
        _risco(1, tipo=Tipo.DEMANDA_SEM_EVIDENCIA)
        _risco(2, tipo=Tipo.DEMANDA_SEM_EVIDENCIA)

        assert GlosaRisk.objects.count() == 2

    def test_a_mesma_demanda_sem_evidencia_nao_duplica(self):
        _risco(1, tipo=Tipo.DEMANDA_SEM_EVIDENCIA)

        with pytest.raises(IntegrityError), transaction.atomic():
            _risco(1, tipo=Tipo.DEMANDA_SEM_EVIDENCIA)

    def test_o_mesmo_pagamento_da_mesma_importacao_nao_duplica(self):
        _risco(1, solicitacao="9")

        with pytest.raises(IntegrityError), transaction.atomic():
            _risco(1, solicitacao="9")

    def test_pago_acima_e_sem_evidencia_convivem_na_mesma_demanda(self):
        _risco(1, solicitacao="9")
        _risco(1, tipo=Tipo.DEMANDA_SEM_EVIDENCIA)

        assert GlosaRisk.objects.count() == 2
