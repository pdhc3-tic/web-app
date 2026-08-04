import pytest

from apps.sgp.constants import (
    AGUA_CHOICES,
    COR_RACA_CHOICES,
    DISPOSITIVO_CHOICES,
    ENERGIA_CHOICES,
    ESCOLARIDADE_CHOICES,
    GENERO_CHOICES,
    MATERIAL_CONSTRUCAO_CHOICES,
    PARENTESCO_CHOICES,
    PCT_CHOICES,
    POSSE_TERRA_CHOICES,
    SAUDE_CHOICES,
    SITUACAO_MORADIA_CHOICES,
    TIPO_MORADIA_CHOICES,
)

pytestmark = pytest.mark.django_db


class TestSGPChoicesEndpoint:
    CHOICES_URL = "/api/v1/choices/"

    def test_requires_authentication(self, api_client):
        response = api_client.get(self.CHOICES_URL)
        assert response.status_code == 401

    def test_returns_all_expected_keys(self, auth_client):
        response = auth_client.get(self.CHOICES_URL)
        assert response.status_code == 200

        expected_keys = {
            "genero", "cor_raca", "escolaridade", "dispositivo",
            "pct", "posse_terra", "situacao_moradia", "tipo_moradia",
            "material_construcao", "energia", "agua",
            "parentesco", "saude",
        }
        assert set(response.data.keys()) == expected_keys

    def test_genero_choices_structure(self, auth_client):
        response = auth_client.get(self.CHOICES_URL)
        assert response.status_code == 200

        genero = response.data["genero"]
        assert isinstance(genero, list)
        assert len(genero) == len(GENERO_CHOICES)

        for item, (value, label) in zip(genero, GENERO_CHOICES):
            assert item == {"value": value, "label": label}

    def test_cor_raca_choices(self, auth_client):
        response = auth_client.get(self.CHOICES_URL)
        choices = response.data["cor_raca"]
        assert len(choices) == len(COR_RACA_CHOICES)
        for item, (value, label) in zip(choices, COR_RACA_CHOICES):
            assert item == {"value": value, "label": label}

    def test_escolaridade_choices(self, auth_client):
        response = auth_client.get(self.CHOICES_URL)
        choices = response.data["escolaridade"]
        assert len(choices) == len(ESCOLARIDADE_CHOICES)
        for item, (value, label) in zip(choices, ESCOLARIDADE_CHOICES):
            assert item == {"value": value, "label": label}

    def test_dispositivo_choices(self, auth_client):
        response = auth_client.get(self.CHOICES_URL)
        choices = response.data["dispositivo"]
        assert len(choices) == len(DISPOSITIVO_CHOICES)
        for item, (value, label) in zip(choices, DISPOSITIVO_CHOICES):
            assert item == {"value": value, "label": label}

    def test_pct_choices(self, auth_client):
        response = auth_client.get(self.CHOICES_URL)
        choices = response.data["pct"]
        assert len(choices) == len(PCT_CHOICES)
        for item, (value, label) in zip(choices, PCT_CHOICES):
            assert item == {"value": value, "label": label}

    def test_posse_terra_choices(self, auth_client):
        response = auth_client.get(self.CHOICES_URL)
        choices = response.data["posse_terra"]
        assert len(choices) == len(POSSE_TERRA_CHOICES)
        for item, (value, label) in zip(choices, POSSE_TERRA_CHOICES):
            assert item == {"value": value, "label": label}

    def test_situacao_moradia_choices(self, auth_client):
        response = auth_client.get(self.CHOICES_URL)
        choices = response.data["situacao_moradia"]
        assert len(choices) == len(SITUACAO_MORADIA_CHOICES)
        for item, (value, label) in zip(choices, SITUACAO_MORADIA_CHOICES):
            assert item == {"value": value, "label": label}

    def test_tipo_moradia_choices(self, auth_client):
        response = auth_client.get(self.CHOICES_URL)
        choices = response.data["tipo_moradia"]
        assert len(choices) == len(TIPO_MORADIA_CHOICES)
        for item, (value, label) in zip(choices, TIPO_MORADIA_CHOICES):
            assert item == {"value": value, "label": label}

    def test_material_construcao_choices(self, auth_client):
        response = auth_client.get(self.CHOICES_URL)
        choices = response.data["material_construcao"]
        assert len(choices) == len(MATERIAL_CONSTRUCAO_CHOICES)
        for item, (value, label) in zip(choices, MATERIAL_CONSTRUCAO_CHOICES):
            assert item == {"value": value, "label": label}

    def test_energia_choices(self, auth_client):
        response = auth_client.get(self.CHOICES_URL)
        choices = response.data["energia"]
        assert len(choices) == len(ENERGIA_CHOICES)
        for item, (value, label) in zip(choices, ENERGIA_CHOICES):
            assert item == {"value": value, "label": label}

    def test_agua_choices(self, auth_client):
        response = auth_client.get(self.CHOICES_URL)
        choices = response.data["agua"]
        assert len(choices) == len(AGUA_CHOICES)
        for item, (value, label) in zip(choices, AGUA_CHOICES):
            assert item == {"value": value, "label": label}

    def test_parentesco_choices_structure(self, auth_client):
        response = auth_client.get(self.CHOICES_URL)
        choices = response.data["parentesco"]
        assert len(choices) == len(PARENTESCO_CHOICES)
        for item, (value, label) in zip(choices, PARENTESCO_CHOICES):
            assert item == {"value": value, "label": label}

    def test_saude_choices_uses_value_as_label(self, auth_client):
        response = auth_client.get(self.CHOICES_URL)
        choices = response.data["saude"]
        assert len(choices) == len(SAUDE_CHOICES)
        for item, value in zip(choices, SAUDE_CHOICES):
            assert item == {"value": value, "label": value}

    def test_all_choices_have_value_and_label_keys(self, auth_client):
        response = auth_client.get(self.CHOICES_URL)
        for key, items in response.data.items():
            for item in items:
                assert "value" in item, f"Missing 'value' in {key}[{items.index(item)}]"
                assert "label" in item, f"Missing 'label' in {key}[{items.index(item)}]"
