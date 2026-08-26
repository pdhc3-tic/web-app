import csv
from datetime import datetime
from io import StringIO

import pytest
from django.utils import timezone

from apps.sgp.tests.factories import FormResponseFactory


pytestmark = pytest.mark.django_db


def export_url(upf):
    return f"/api/v1/sgp/upfs/{upf.pk}/formularios/exportar/"


def aware(year, month, day):
    return timezone.make_aware(datetime(year, month, day, 12, 0))


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
