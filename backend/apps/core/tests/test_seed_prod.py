import hashlib
import json
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from openpyxl import Workbook

from apps.core.models import Municipality, State, Territory
from apps.sgp.models import Comunidade, Cultura, EspecieAnimal


def workbook(path, sheets):
    book = Workbook()
    book.remove(book.active)
    for name, rows in sheets.items():
        sheet = book.create_sheet(name)
        for row in rows:
            sheet.append(row)
    book.save(path)


def prepare_package(source_dir, package_dir):
    call_command(
        "prepare_seed",
        "--source-dir",
        str(source_dir),
        "--output-dir",
        str(package_dir),
    )


@pytest.fixture
def legacy_seed_dir(tmp_path):
    workbook(
        tmp_path / "municipios.xlsx",
        {
            "Estados": [
                ["Estado", "Nome"],
                ["RN", "Rio Grande do Norte"],
            ],
            "Municípios": [
                ["Row ID", "Município", "Estado", "Território", "Bioma"],
                [2408003, "Mossoró", "RN", 1, "Caatinga"],
            ],
            "Municipios_Dados": [
                [
                    "Row ID",
                    "Município",
                    "Área",
                    "População Total",
                    "População Rural",
                    "IDH",
                    "% de Extremamente Pobres",
                    "Beneficiários do Agricultura Familiar",
                    "Estabelecimentos Agricultura Familiar",
                ],
                [2408003, 2408003, 2109.0, 264577, 12000, 6260, 16.0, 5247, 561],
            ],
        },
    )
    workbook(
        tmp_path / "comunidades.xlsx",
        {
            "Territórios": [
                ["Row ID", "Território", "Estados"],
                [1, "Açu-Mossoró", "RN"],
            ],
            "Comunidades": [
                ["Row ID", "Comunidade", "Localização Geográfica", "Município"],
                ["legacy-community", "Baraúna", "-5.2, -37.3", 2408003],
            ],
        },
    )
    workbook(
        tmp_path / "culturaseanimais.xlsx",
        {
            "Culturas": [
                ["Row ID", "Cultura", "Tipo"],
                ["legacy-crop", "Mamão", "Fruticultura"],
            ],
            "Pecuária": [
                ["Row ID", "Pecuária", "Espécie"],
                ["legacy-animal", "Bovino", None],
            ],
            "Sementes Crioulas": [
                ["Semente"],
                ["Abobrinha"],
            ],
        },
    )
    workbook(
        tmp_path / "SGP.xlsx",
        {
            "Pessoas": [
                ["ID", "Nome", "Email", "Telefone"],
                ["legacy-person", "Pessoa Legada", "pessoa@exemplo.test", 84999990000],
            ],
            "Metas": [
                ["ID", "Projeto", "Número", "Meta"],
                ["legacy-meta", "legacy-project", None, "Meta legada"],
            ],
        },
    )
    return tmp_path


@pytest.mark.django_db
def test_seed_prod_is_idempotent(legacy_seed_dir):
    package_dir = legacy_seed_dir / "package"
    prepare_package(legacy_seed_dir, package_dir)
    first_output = StringIO()
    call_command(
        "seed_prod",
        "--package-dir",
        str(package_dir),
        stdout=first_output,
    )

    second_output = StringIO()
    call_command(
        "seed_prod",
        "--package-dir",
        str(package_dir),
        stdout=second_output,
    )

    assert State.objects.filter(sigla="RN").count() == 1
    assert Territory.objects.filter(nome="Açu-Mossoró").count() == 1
    assert Municipality.objects.filter(codigo_ibge="2408003").count() == 1
    assert Comunidade.objects.filter(nome="Baraúna").count() == 1
    assert Cultura.objects.filter(nome="Mamão").count() == 1
    assert EspecieAnimal.objects.filter(nome="Bovino").count() == 1
    assert get_user_model().objects.filter(email="pessoa@exemplo.test").count() == 1
    assert "states.created: 1" in first_output.getvalue()
    assert "states.updated: 1" in second_output.getvalue()
    assert "sheets_not_supported" in first_output.getvalue()


@pytest.mark.django_db
def test_seed_prod_dry_run_does_not_persist(legacy_seed_dir):
    package_dir = legacy_seed_dir / "package"
    prepare_package(legacy_seed_dir, package_dir)
    output = StringIO()
    call_command(
        "seed_prod",
        "--package-dir",
        str(package_dir),
        "--dry-run",
        stdout=output,
    )

    assert State.objects.count() == 0
    assert Municipality.objects.count() == 0
    assert "Dry-run concluído" in output.getvalue()


@pytest.mark.django_db
def test_seed_prod_reports_existing_records_absent_from_source(legacy_seed_dir):
    package_dir = legacy_seed_dir / "package"
    prepare_package(legacy_seed_dir, package_dir)
    State.objects.create(sigla="XX", nome="Fora da planilha")
    output = StringIO()

    call_command(
        "seed_prod",
        "--package-dir",
        str(package_dir),
        "--dry-run",
        stdout=output,
    )

    assert "states.missing: 1" in output.getvalue()
    assert "XX" in output.getvalue()


@pytest.mark.django_db
def test_seed_prod_rejects_modified_package(legacy_seed_dir):
    package_dir = legacy_seed_dir / "package"
    prepare_package(legacy_seed_dir, package_dir)
    states_path = package_dir / "states.jsonl"
    states_path.write_text(states_path.read_text() + "\n", encoding="utf-8")

    with pytest.raises(CommandError, match="Hash inválido"):
        call_command("seed_prod", "--package-dir", str(package_dir))


@pytest.mark.django_db
def test_seed_prod_keeps_identity_when_source_data_changes(legacy_seed_dir):
    package_dir = legacy_seed_dir / "package"
    prepare_package(legacy_seed_dir, package_dir)
    call_command("seed_prod", "--package-dir", str(package_dir))

    people_path = package_dir / "people.jsonl"
    person = json.loads(people_path.read_text(encoding="utf-8"))
    person["data"]["nome"] = "Nome atualizado"
    people_path.write_text(
        json.dumps(person, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest_path = package_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["people.jsonl"]["sha256"] = hashlib.sha256(
        people_path.read_bytes()
    ).hexdigest()
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    call_command("seed_prod", "--package-dir", str(package_dir))

    user = get_user_model().objects.get(email="pessoa@exemplo.test")
    assert user.nome == "Nome atualizado"
    assert get_user_model().objects.filter(email="pessoa@exemplo.test").count() == 1


@pytest.mark.django_db
def test_ensure_superuser_is_idempotent_without_resetting_password():
    call_command(
        "ensure_superuser",
        email="admin@deploy.test",
        name="Administrador",
        password="OriginalPassword123!",
    )
    user = get_user_model().objects.get(email="admin@deploy.test")
    user.set_password("ChangedPassword123!")
    user.save(update_fields=["password"])

    call_command(
        "ensure_superuser",
        email="admin@deploy.test",
        name="Outro nome",
        password="NewPassword123!",
    )

    user.refresh_from_db()
    assert user.is_superuser is True
    assert user.check_password("ChangedPassword123!")
    assert user.nome == "Administrador"
