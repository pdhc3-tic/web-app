import pytest

from apps.sgp import constants
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
    SEGURIDADE_SOCIAL_CHOICES,
    SITUACAO_MORADIA_CHOICES,
    TIPO_MORADIA_CHOICES,
)
from apps.sgp.views.choices import CHOICES_PUBLICADOS

pytestmark = pytest.mark.django_db


class TestSGPChoicesEndpoint:
    CHOICES_URL = "/api/v1/choices/"

    def test_requires_authentication(self, api_client):
        response = api_client.get(self.CHOICES_URL)
        assert response.status_code == 401

    def test_returns_all_expected_keys(self, auth_client):
        response = auth_client.get(self.CHOICES_URL)
        assert response.status_code == 200

        assert set(response.data.keys()) == set(CHOICES_PUBLICADOS)

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
        choices = response.data["grau_parentesco"]
        assert len(choices) == len(PARENTESCO_CHOICES)
        for item, (value, label) in zip(choices, PARENTESCO_CHOICES):
            assert item == {"value": value, "label": label}

    def test_saude_choices_tem_rotulo_legivel(self, auth_client):
        response = auth_client.get(self.CHOICES_URL)
        choices = response.data["saude"]
        assert len(choices) == len(SAUDE_CHOICES)
        for item, (value, label) in zip(choices, SAUDE_CHOICES):
            assert item == {"value": value, "label": label}
        assert {"value": "deficiencia_visual", "label": "Deficiência visual"} in choices

    def test_seguridade_social_choices(self, auth_client):
        response = auth_client.get(self.CHOICES_URL)
        choices = response.data["seguridade_social"]
        assert len(choices) == len(SEGURIDADE_SOCIAL_CHOICES)
        for item, (value, label) in zip(choices, SEGURIDADE_SOCIAL_CHOICES):
            assert item == {"value": value, "label": label}

    @pytest.mark.parametrize("chave", [
        "ods", "status_plano_trabalho", "tipo_atividade", "forma_atuacao", "ambito",
        "status_atividade", "producao_tipo", "producao_sistema_criacao",
        "producao_tipo_outra", "upf_documento_tipo", "atividade_documento_tipo",
    ])
    def test_listas_de_atividade_producao_ods_e_documentos(self, auth_client, chave):
        response = auth_client.get(self.CHOICES_URL)
        esperado = [{"value": v, "label": l} for v, l in CHOICES_PUBLICADOS[chave]]
        assert response.data[chave] == esperado
        assert esperado

    def test_all_choices_have_value_and_label_keys(self, auth_client):
        response = auth_client.get(self.CHOICES_URL)
        for key, items in response.data.items():
            for item in items:
                assert "value" in item, f"Missing 'value' in {key}[{items.index(item)}]"
                assert "label" in item, f"Missing 'label' in {key}[{items.index(item)}]"


def test_choices_expoe_todas_as_constantes():
    """Constante de choices nova em `constants.py` que não entre no endpoint
    derruba este teste."""
    publicadas = [id(opcoes) for opcoes in CHOICES_PUBLICADOS.values()]
    constantes = {
        nome: valor for nome, valor in vars(constants).items()
        if nome.endswith("_CHOICES") or nome == "STATUS_WORKPLAN"
    }
    assert constantes
    ausentes = [nome for nome, valor in constantes.items() if id(valor) not in publicadas]
    assert not ausentes, f"Constantes fora do endpoint /choices/: {ausentes}"
