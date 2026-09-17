from io import BytesIO

import pytest
from pypdf import PdfReader

from apps.sgp.tests.factories import FormResponseFactory

pytestmark = pytest.mark.django_db


def export_url(upf):
    return f"/api/v1/sgp/upfs/{upf.pk}/formularios/exportar/"


def extract_pages_text(response) -> list[str]:
    content = b"".join(response.streaming_content)
    reader = PdfReader(BytesIO(content))
    return [page.extract_text() or "" for page in reader.pages]


def extract_text(response) -> str:
    return "\n".join(extract_pages_text(response))


def test_pdf_uses_humanized_labels_instead_of_raw_json_keys(auth_client, upf):
    FormResponseFactory(upf=upf, respostas_json={"renda_familiar": 1200})

    response = auth_client.get(export_url(upf), {"formato": "pdf"})
    text = extract_text(response)

    assert "Renda familiar" in text
    assert "1200" in text
    assert '"renda_familiar"' not in text


def test_pdf_renders_boolean_as_sim_nao(auth_client, upf):
    FormResponseFactory(
        upf=upf, respostas_json={"possui_energia": True, "possui_agua": False}
    )

    response = auth_client.get(export_url(upf), {"formato": "pdf"})
    text = extract_text(response)

    assert "Sim" in text
    assert "Não" in text


def test_pdf_renders_primitive_list_as_inline_chips(auth_client, upf):
    FormResponseFactory(
        upf=upf, respostas_json={"culturas": ["Milho", "Feijão", "Mandioca"]}
    )

    response = auth_client.get(export_url(upf), {"formato": "pdf"})
    text = extract_text(response)

    assert "Milho" in text
    assert "Feijão" in text
    assert "Mandioca" in text


def test_pdf_renders_repeatable_group_with_numbered_items(auth_client, upf):
    FormResponseFactory(
        upf=upf,
        respostas_json={"membros_familia": [{"nome": "Ana"}, {"nome": "Beto"}]},
    )

    response = auth_client.get(export_url(upf), {"formato": "pdf"})
    text = extract_text(response)

    assert "Item 1" in text
    assert "Item 2" in text
    assert "Ana" in text
    assert "Beto" in text


def test_pdf_renders_nested_object_as_titled_subsection(auth_client, upf):
    FormResponseFactory(
        upf=upf,
        respostas_json={"endereco": {"municipio": "Mossoró", "estado": "RN"}},
    )

    response = auth_client.get(export_url(upf), {"formato": "pdf"})
    text = extract_text(response)

    assert "Endereco" in text
    assert "Mossoró" in text
    assert "RN" in text


def test_pdf_renders_unanswered_field_as_em_dash(auth_client, upf):
    FormResponseFactory(upf=upf, respostas_json={"observacoes": None})

    response = auth_client.get(export_url(upf), {"formato": "pdf"})
    text = extract_text(response)

    assert "Observacoes" in text
    assert "—" in text


def test_pdf_shows_empty_state_message_for_response_without_answers(auth_client, upf):
    FormResponseFactory(upf=upf, respostas_json={})

    response = auth_client.get(export_url(upf), {"formato": "pdf"})
    text = extract_text(response)

    assert "Este formulário foi submetido sem respostas registradas." in text


def test_pdf_renders_accented_and_unicode_characters(auth_client, upf):
    FormResponseFactory(
        upf=upf,
        respostas_json={"observação": "Café, açúcar, pão — condição precária"},
    )

    response = auth_client.get(export_url(upf), {"formato": "pdf"})
    text = extract_text(response)

    assert "Café, açúcar, pão" in text
    assert "condição precária" in text


def test_pdf_keeps_multiple_responses_independent_across_pages(auth_client, upf):
    FormResponseFactory(
        upf=upf,
        formulario_nome="Formulário A",
        formulario_versao="1.0",
        respostas_json={"marcador_a": "valor-unico-A"},
    )
    FormResponseFactory(
        upf=upf,
        formulario_nome="Formulário B",
        formulario_versao="2.0",
        respostas_json={"marcador_b": "valor-unico-B"},
    )

    response = auth_client.get(export_url(upf), {"formato": "pdf"})
    pages = extract_pages_text(response)

    page_a = next(page for page in pages if "valor-unico-A" in page)
    page_b = next(page for page in pages if "valor-unico-B" in page)

    assert "Formulário A" in page_a
    assert "valor-unico-B" not in page_a

    assert "Formulário B" in page_b
    assert "valor-unico-A" not in page_b


def test_pdf_does_not_contain_raw_json_dump_as_sole_representation(auth_client, upf):
    FormResponseFactory(upf=upf, respostas_json={"pergunta_1": "resposta"})

    response = auth_client.get(export_url(upf), {"formato": "pdf"})
    text = extract_text(response)

    assert '"pergunta_1"' not in text
    assert "Pergunta 1" in text
    assert "resposta" in text
