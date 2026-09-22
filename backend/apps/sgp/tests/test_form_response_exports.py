import csv
import json
from datetime import datetime
from io import BytesIO, StringIO

import pytest
from django.utils import timezone
from pypdf import PdfReader

from apps.sgp.tests.factories import FormResponseFactory, UPFFactory


pytestmark = pytest.mark.django_db


def export_url(upf):
    return f"/api/v1/sgp/upfs/{upf.pk}/formularios/exportar/"


def list_url(upf):
    return f"/api/v1/sgp/upfs/{upf.pk}/formularios/"


def aware(year, month, day):
    return timezone.make_aware(datetime(year, month, day, 12, 0))


def extract_pages_text(response) -> list[str]:
    content = b"".join(response.streaming_content)
    reader = PdfReader(BytesIO(content))
    return [page.extract_text() or "" for page in reader.pages]


def extract_text(response) -> str:
    return "\n".join(extract_pages_text(response))


def test_csv_exports_one_row_per_filtered_response_with_metadata(auth_client, upf):
    expected = FormResponseFactory(
        upf=upf,
        formulario_id=7,
        formulario_nome="Diagnóstico da UPF",
        formulario_versao="2.0",
        respondente="Maria Silva",
        respostas_json={"renda": 1200},
    )
    FormResponseFactory(upf=upf, formulario_id=8)

    response = auth_client.get(
        export_url(upf),
        {"formato": "csv", "formulario_id": expected.formulario_id},
    )

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    rows = list(csv.DictReader(StringIO(response.content.decode("utf-8-sig"))))
    assert len(rows) == 1
    assert rows[0] == {
        "ID": str(expected.pk),
        "Formulário": "Diagnóstico da UPF",
        "Versão": "2.0",
        "Data de preenchimento": timezone.localtime(
            expected.data_preenchimento
        ).isoformat(),
        "Respondente": "Maria Silva",
        "Status": "Submetido",
        "Origem": "Web",
        "Respostas": '{"renda": 1200}',
    }


def test_pdf_exports_multiple_form_responses(auth_client, upf):
    FormResponseFactory(upf=upf, formulario_nome="Formulário A")
    FormResponseFactory(upf=upf, formulario_nome="Formulário B")

    response = auth_client.get(export_url(upf), {"formato": "pdf"})

    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response["Content-Disposition"].endswith('.pdf"')
    assert b"".join(response.streaming_content).startswith(b"%PDF-")


def test_export_rejects_unsupported_format(auth_client, upf):
    response = auth_client.get(export_url(upf), {"formato": "xlsx"})

    assert response.status_code == 400
    assert "formato" in response.data


def test_export_respects_respondente_isnull_filter(auth_client, upf):
    anonima = FormResponseFactory(upf=upf, respondente=None)
    FormResponseFactory(upf=upf, respondente="Maria Silva")

    response = auth_client.get(
        export_url(upf),
        {"formato": "csv", "respondente_isnull": "true"},
    )

    assert response.status_code == 200
    rows = list(csv.DictReader(StringIO(response.content.decode("utf-8-sig"))))
    assert [row["ID"] for row in rows] == [str(anonima.pk)]
    assert rows[0]["Respondente"] == "Anônimo"


def test_export_matches_filtered_list_for_respondente_isnull(auth_client, upf):
    FormResponseFactory(upf=upf, respondente=None)
    FormResponseFactory(upf=upf, respondente=None)
    FormResponseFactory(upf=upf, respondente="Maria Silva")

    filtros = {"respondente_isnull": "true"}
    listagem = auth_client.get(list_url(upf), filtros)
    exportacao = auth_client.get(export_url(upf), {**filtros, "formato": "csv"})

    ids_lista = {item["id"] for item in listagem.data["results"]}
    ids_exportacao = {
        int(row["ID"])
        for row in csv.DictReader(StringIO(exportacao.content.decode("utf-8-sig")))
    }
    assert len(ids_lista) == 2
    assert ids_exportacao == ids_lista


def test_export_respects_completion_period_filter(auth_client, upf):
    before = FormResponseFactory(upf=upf, data_preenchimento=aware(2026, 1, 10))
    expected = FormResponseFactory(upf=upf, data_preenchimento=aware(2026, 2, 15))
    after = FormResponseFactory(upf=upf, data_preenchimento=aware(2026, 3, 10))

    response = auth_client.get(
        export_url(upf),
        {
            "formato": "csv",
            "data_inicio": "2026-02-01",
            "data_fim": "2026-02-28",
        },
    )

    rows = list(csv.DictReader(StringIO(response.content.decode("utf-8-sig"))))
    assert response.status_code == 200
    assert [row["ID"] for row in rows] == [str(expected.pk)]
    assert str(before.pk) not in [row["ID"] for row in rows]
    assert str(after.pk) not in [row["ID"] for row in rows]


def test_pdf_export_renderiza_grupos_aninhados_profundos_via_endpoint(auth_client, upf):
    FormResponseFactory(
        upf=upf,
        respostas_json={
            "propriedade": {
                "endereco": {
                    "lotes": [
                        {"nome": "Lote A", "area_ha": 2.5},
                        {"nome": "Lote B", "area_ha": 1.1},
                    ]
                }
            }
        },
    )

    response = auth_client.get(export_url(upf), {"formato": "pdf"})
    text = extract_text(response)

    assert response.status_code == 200
    for esperado in [
        "Propriedade",
        "Endereco",
        "Lotes",
        "Item 1",
        "Item 2",
        "Lote A",
        "Lote B",
        "2.5",
        "1.1",
    ]:
        assert esperado in text
    assert text.index("Propriedade") < text.index("Endereco") < text.index("Lotes")
    assert text.index("Item 1") < text.index("Item 2")


def test_pdf_export_renderiza_lista_mista_de_primitivos_e_dict_como_grupo(
    auth_client, upf
):
    FormResponseFactory(
        upf=upf,
        respostas_json={
            "participantes": [
                "João",
                "Maria",
                {"nome": "Pedro", "papel": "convidado"},
            ]
        },
    )

    response = auth_client.get(export_url(upf), {"formato": "pdf"})
    text = extract_text(response)

    assert response.status_code == 200
    assert "João" in text
    assert "Maria" in text
    assert "Pedro" in text
    assert "convidado" in text
    # Lista com um dict misturado a primitivos vira grupo numerado
    # (Item 1/2/3), não uma lista de chips inline.
    assert "Item 1" in text
    assert "Item 2" in text
    assert "Item 3" in text


def test_pdf_export_exibe_em_dash_para_campos_vazios_em_resposta_parcial_via_endpoint(
    auth_client, upf
):
    FormResponseFactory(
        upf=upf,
        respostas_json={
            "nome": "Maria",
            "telefone": None,
            "documentos": [],
        },
    )

    response = auth_client.get(export_url(upf), {"formato": "pdf"})
    text = extract_text(response)

    assert response.status_code == 200
    assert "Maria" in text
    assert "Telefone" in text
    assert "Documentos" in text
    assert text.count("—") >= 2


def test_csv_export_serializa_respostas_json_aninhado_sem_perda(auth_client, upf):
    payload = {
        "endereco": {"rua": "Rua A", "numero": 10},
        "contatos": ["a@x.com", "b@x.com"],
    }
    FormResponseFactory(upf=upf, respostas_json=payload)

    response = auth_client.get(export_url(upf), {"formato": "csv"})
    rows = list(csv.DictReader(StringIO(response.content.decode("utf-8-sig"))))

    assert response.status_code == 200
    assert len(rows) == 1
    assert json.loads(rows[0]["Respostas"]) == payload


def test_pdf_export_escapa_caracteres_de_markup_xml_em_respostas(auth_client, upf):
    FormResponseFactory(
        upf=upf,
        respostas_json={"observacao": 'Renda < 1000 & area > 5 hectares "citada"'},
    )

    response = auth_client.get(export_url(upf), {"formato": "pdf"})

    assert response.status_code == 200
    text = extract_text(response)
    assert "Renda < 1000 & area > 5 hectares" in text


def test_pdf_export_pagina_resposta_com_texto_muito_longo_e_mantem_extraivel(
    auth_client, upf
):
    texto_longo = "Lorem ipsum dolor sit amet consectetur adipiscing elit. " * 60
    assert len(texto_longo) > 2000
    FormResponseFactory(upf=upf, respostas_json={"relato": texto_longo})

    response = auth_client.get(export_url(upf), {"formato": "pdf"})

    assert response.status_code == 200
    pages = extract_pages_text(response)
    assert len(pages) >= 1
    full_text = "\n".join(pages)
    assert full_text.count("Lorem ipsum") >= 2
    assert "elit." in full_text


def test_pdf_export_nao_contem_json_bruto_indentado_regressao_205(auth_client, upf):
    """Teste de trava permanente para a issue #205.

    A correção (renderização estruturada em vez de JSON bruto) já foi
    mergeada via PR #259 antes desta issue #270 existir — não é mais
    possível reproduzir o estado "antes da correção". Este teste apenas
    garante que a regressão não volta a acontecer.
    """
    respostas = {"pergunta_1": "resposta", "idade": 34, "ativo": True}
    FormResponseFactory(upf=upf, respostas_json=respostas)

    response = auth_client.get(export_url(upf), {"formato": "pdf"})
    text = extract_text(response)

    assert response.status_code == 200
    assert '"pergunta_1"' not in text
    assert json.dumps(respostas, indent=2) not in text
    assert "Pergunta 1" in text
    assert "resposta" in text


def test_pdf_export_respeita_filtro_respondente_isnull(auth_client, upf):
    FormResponseFactory(
        upf=upf, respondente=None, respostas_json={"marcador": "anonimo-x"}
    )
    FormResponseFactory(
        upf=upf, respondente="Maria Silva", respostas_json={"marcador": "nomeada-y"}
    )

    response = auth_client.get(
        export_url(upf), {"formato": "pdf", "respondente_isnull": "true"}
    )
    text = extract_text(response)

    assert response.status_code == 200
    assert "anonimo-x" in text
    assert "nomeada-y" not in text
    assert "Anônimo" in text


def test_pdf_export_respeita_filtro_de_periodo_de_preenchimento(auth_client, upf):
    FormResponseFactory(
        upf=upf,
        formulario_nome="Fora do período",
        data_preenchimento=aware(2026, 1, 10),
    )
    FormResponseFactory(
        upf=upf,
        formulario_nome="Dentro do período",
        data_preenchimento=aware(2026, 2, 15),
    )
    FormResponseFactory(
        upf=upf,
        formulario_nome="Depois do período",
        data_preenchimento=aware(2026, 3, 10),
    )

    response = auth_client.get(
        export_url(upf),
        {"formato": "pdf", "data_inicio": "2026-02-01", "data_fim": "2026-02-28"},
    )
    text = extract_text(response)

    assert response.status_code == 200
    assert "Dentro do período" in text
    assert "Fora do período" not in text
    assert "Depois do período" not in text


def test_pdf_export_mantem_versoes_diferentes_do_mesmo_formulario_separadas(
    auth_client, upf
):
    FormResponseFactory(
        upf=upf,
        formulario_id=7,
        formulario_nome="Diagnóstico",
        formulario_versao="1.0",
        respostas_json={"marcador": "versao-um"},
    )
    FormResponseFactory(
        upf=upf,
        formulario_id=7,
        formulario_nome="Diagnóstico",
        formulario_versao="2.0",
        respostas_json={"marcador": "versao-dois"},
    )

    response = auth_client.get(export_url(upf), {"formato": "pdf"})
    pages = extract_pages_text(response)

    page_v1 = next(page for page in pages if "versao-um" in page)
    page_v2 = next(page for page in pages if "versao-dois" in page)

    assert "Diagnóstico (v1.0)" in page_v1
    assert "versao-dois" not in page_v1
    assert "Diagnóstico (v2.0)" in page_v2
    assert "versao-um" not in page_v2


def test_pdf_export_de_upf_fora_do_territorio_retorna_404(
    auth_client_adt_rn, projeto, municipio_ce, territory_ce
):
    upf_ce = UPFFactory(
        projeto=projeto,
        municipio=municipio_ce,
        territorio=territory_ce,
        titular_cpf="52998224725",
    )
    FormResponseFactory(upf=upf_ce)

    response = auth_client_adt_rn.get(export_url(upf_ce), {"formato": "pdf"})

    assert response.status_code == 404


def test_pdf_export_respeita_filtro_formulario_id(auth_client, upf):
    esperado = FormResponseFactory(
        upf=upf,
        formulario_id=42,
        formulario_nome="Formulário Alvo",
        respostas_json={"marcador": "alvo-marcado"},
    )
    FormResponseFactory(
        upf=upf,
        formulario_id=43,
        formulario_nome="Formulário Outro",
        respostas_json={"marcador": "outro-marcado"},
    )

    response = auth_client.get(
        export_url(upf), {"formato": "pdf", "formulario_id": esperado.formulario_id}
    )
    text = extract_text(response)

    assert response.status_code == 200
    assert "alvo-marcado" in text
    assert "outro-marcado" not in text


def test_csv_export_preserva_virgulas_e_quebras_de_linha_em_respostas(
    auth_client, upf
):
    payload = {"observacao": "Linha um,\ncom vírgula e quebra de linha"}
    FormResponseFactory(upf=upf, respostas_json=payload)

    response = auth_client.get(export_url(upf), {"formato": "csv"})
    rows = list(csv.DictReader(StringIO(response.content.decode("utf-8-sig"))))

    assert response.status_code == 200
    assert len(rows) == 1
    assert json.loads(rows[0]["Respostas"]) == payload
