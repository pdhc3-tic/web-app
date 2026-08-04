import pytest

from apps.core.models.audit_log import AuditLog
from apps.sgp.models import Production
from apps.sgp.tests.factories import (
    CulturaFactory,
    EspecieAnimalFactory,
    ProductionFactory,
    UPFFactory,
)


pytestmark = pytest.mark.django_db


def producao_url(upf):
    return f"/api/v1/upfs/{upf.pk}/producao/"


def producao_detail_url(upf, production):
    return f"/api/v1/upfs/{upf.pk}/producao/{production.pk}/"


def response_results(response):
    if isinstance(response.data, dict) and "results" in response.data:
        return response.data["results"]
    return response.data


def agricultura_payload(cultura, **overrides):
    payload = {
        "tipo": "agricola",
        "cultura_id": cultura.pk,
        "area_ha": "1.50",
        "producao_estimada": "30.00",
        "unidade_producao": "saca",
        "sementes_crioulas": True,
        "custo_anual": "1200.00",
        "observacoes": "Produção de sequeiro",
    }
    payload.update(overrides)
    return payload


def pecuaria_payload(especie, **overrides):
    payload = {
        "tipo": "pecuaria",
        "especie_id": especie.pk,
        "n_matrizes": 10,
        "n_reprodutores": 1,
        "n_jovens": 4,
        "area_pastejo_ha": "3.00",
        "sistema_criacao": "extensivo",
        "custo_anual": "800.00",
    }
    payload.update(overrides)
    return payload


def outra_payload(**overrides):
    payload = {
        "tipo": "outra",
        "tipo_outra": "artesanato",
        "descricao_outra": "Produção artesanal familiar",
        "quantidade_produzida": "20 peças/mês",
        "renda_estimada_mensal": "600.00",
        "custo_anual": "500.00",
    }
    payload.update(overrides)
    return payload


def test_create_producao_agricola_with_cultura(auth_client, upf):
    cultura = CulturaFactory(nome="Milho", categoria="graos")

    response = auth_client.post(
        producao_url(upf),
        agricultura_payload(cultura),
        format="json",
    )

    assert response.status_code == 201
    assert response.data["tipo"] == "agricola"
    assert response.data["cultura"] == {
        "id": cultura.pk,
        "nome": "Milho",
        "categoria": "graos",
    }
    assert response.data["especie"] is None


def test_create_producao_agricola_without_cultura_returns_400(auth_client, upf):
    response = auth_client.post(
        producao_url(upf),
        {"tipo": "agricola"},
        format="json",
    )

    assert response.status_code == 400
    assert "cultura_id" in response.data


def test_create_producao_agricola_with_especie_returns_400(auth_client, upf):
    cultura = CulturaFactory()
    especie = EspecieAnimalFactory()

    response = auth_client.post(
        producao_url(upf),
        agricultura_payload(cultura, especie_id=especie.pk),
        format="json",
    )

    assert response.status_code == 400
    assert "especie_id" in response.data


def test_create_producao_pecuaria_with_especie(auth_client, upf):
    especie = EspecieAnimalFactory(nome="Caprino", categoria="caprino")

    response = auth_client.post(
        producao_url(upf),
        pecuaria_payload(especie),
        format="json",
    )

    assert response.status_code == 201
    assert response.data["tipo"] == "pecuaria"
    assert response.data["especie"] == {
        "id": especie.pk,
        "nome": "Caprino",
        "categoria": "caprino",
    }
    assert response.data["cultura"] is None


def test_create_producao_pecuaria_without_especie_returns_400(auth_client, upf):
    response = auth_client.post(
        producao_url(upf),
        {"tipo": "pecuaria"},
        format="json",
    )

    assert response.status_code == 400
    assert "especie_id" in response.data


def test_create_producao_pecuaria_with_cultura_returns_400(auth_client, upf):
    especie = EspecieAnimalFactory()
    cultura = CulturaFactory()

    response = auth_client.post(
        producao_url(upf),
        pecuaria_payload(especie, cultura_id=cultura.pk),
        format="json",
    )

    assert response.status_code == 400
    assert "cultura_id" in response.data


def test_create_producao_outra_with_tipo(auth_client, upf):
    response = auth_client.post(
        producao_url(upf),
        outra_payload(),
        format="json",
    )

    assert response.status_code == 201
    assert response.data["tipo"] == "outra"
    assert response.data["tipo_outra"] == "artesanato"
    assert response.data["cultura"] is None
    assert response.data["especie"] is None


def test_create_producao_outra_without_tipo_outra_returns_400(auth_client, upf):
    response = auth_client.post(
        producao_url(upf),
        {"tipo": "outra"},
        format="json",
    )

    assert response.status_code == 400
    assert "tipo_outra" in response.data


def test_create_producao_outra_with_cultura_returns_400(auth_client, upf):
    cultura = CulturaFactory()

    response = auth_client.post(
        producao_url(upf),
        outra_payload(cultura_id=cultura.pk),
        format="json",
    )

    assert response.status_code == 400
    assert "cultura_id" in response.data


def test_create_producao_outra_with_especie_returns_400(auth_client, upf):
    especie = EspecieAnimalFactory()

    response = auth_client.post(
        producao_url(upf),
        outra_payload(especie_id=especie.pk),
        format="json",
    )

    assert response.status_code == 400
    assert "especie_id" in response.data


def test_list_producao_only_returns_for_correct_upf(auth_client, upf, outra_upf):
    own_production = ProductionFactory(upf=upf)
    ProductionFactory(upf=outra_upf)

    response = auth_client.get(producao_url(upf))

    assert response.status_code == 200
    ids = {item["id"] for item in response_results(response)}
    assert ids == {own_production.pk}


def test_cross_upf_producao_returns_404(auth_client, upf, outra_upf):
    other_production = ProductionFactory(upf=outra_upf)

    response = auth_client.get(producao_detail_url(upf, other_production))

    assert response.status_code == 404


def test_serializer_expands_cultura_object(auth_client, upf):
    cultura = CulturaFactory(nome="Feijão", categoria="graos")
    production = ProductionFactory(upf=upf, cultura=cultura)

    response = auth_client.get(producao_detail_url(upf, production))

    assert response.status_code == 200
    assert response.data["cultura"] == {
        "id": cultura.pk,
        "nome": "Feijão",
        "categoria": "graos",
    }


def test_serializer_expands_especie_object(auth_client, upf):
    especie = EspecieAnimalFactory(nome="Ovino", categoria="ovino")
    production = Production.objects.create(
        upf=upf,
        tipo=Production.TIPO_PECUARIA,
        especie=especie,
        n_matrizes=5,
    )

    response = auth_client.get(producao_detail_url(upf, production))

    assert response.status_code == 200
    assert response.data["especie"] == {
        "id": especie.pk,
        "nome": "Ovino",
        "categoria": "ovino",
    }


def test_create_producao_for_inactive_upf_returns_400(auth_client, upf_inativa):
    cultura = CulturaFactory()

    response = auth_client.post(
        producao_url(upf_inativa),
        agricultura_payload(cultura),
        format="json",
    )

    assert response.status_code == 400
    assert "UPF inativa" in str(response.data)


def test_adt_other_territory_cannot_create_producao(
    auth_client_adt_rn,
    projeto,
    municipio_ce,
    territory_ce,
):
    upf_ce = UPFFactory(
        projeto=projeto,
        municipio=municipio_ce,
        territorio=territory_ce,
        cpf="52998224725",
    )
    cultura = CulturaFactory()

    response = auth_client_adt_rn.post(
        producao_url(upf_ce),
        agricultura_payload(cultura),
        format="json",
    )

    assert response.status_code == 404


def test_audit_log_on_producao_changes(auth_client, upf):
    cultura = CulturaFactory()

    create_response = auth_client.post(
        producao_url(upf),
        agricultura_payload(cultura),
        format="json",
    )
    production_id = create_response.data["id"]

    auth_client.patch(
        f"/api/v1/upfs/{upf.pk}/producao/{production_id}/",
        {"observacoes": "Observação atualizada"},
        format="json",
    )
    auth_client.delete(f"/api/v1/upfs/{upf.pk}/producao/{production_id}/")

    for action in [
        "production.create",
        "production.update",
        "production.delete",
    ]:
        assert AuditLog.objects.filter(
            acao=action,
            entidade="Production",
            entidade_id=str(production_id),
        ).exists()
