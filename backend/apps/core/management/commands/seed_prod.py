from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.models import (
    Municipality,
    SeedImportRecord,
    State,
    Territory,
)
from apps.core.seed_package import ENTITY_FILES, PACKAGE_VERSION
from apps.sgp.models import Comunidade, Cultura, EspecieAnimal


class DryRunRollback(Exception):
    pass


class PackageReader:
    def __init__(self, package_dir: Path):
        self.package_dir = package_dir
        self.manifest = self._read_json("manifest.json")
        self.report = self._read_json("report.json")
        if not isinstance(self.manifest, dict):
            raise CommandError("Manifesto de seed inválido.")
        if not isinstance(self.report, dict):
            raise CommandError("Relatório de seed inválido.")
        if not isinstance(self.report.get("issues", []), list):
            raise CommandError("Relatório de seed sem uma lista de ocorrências.")
        if self.manifest.get("package_version") != PACKAGE_VERSION:
            raise CommandError("Versão de pacote de seed não suportada.")
        files = self.manifest.get("files")
        if not isinstance(files, dict):
            raise CommandError("Manifesto de seed sem a seção 'files'.")
        for entity, filename in ENTITY_FILES.items():
            metadata = files.get(filename)
            if not isinstance(metadata, dict) or metadata.get("entity") != entity:
                raise CommandError(
                    f"Manifesto de seed sem o arquivo obrigatório: {filename}"
                )

    def _read_json(self, filename: str) -> Any:
        path = self.package_dir / filename
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise CommandError(f"Arquivo obrigatório ausente no pacote: {path}") from exc
        except json.JSONDecodeError as exc:
            raise CommandError(f"JSON inválido no pacote: {path}") from exc

    def records(self, entity: str) -> list[dict[str, Any]]:
        filename = ENTITY_FILES.get(entity)
        if not filename:
            raise CommandError(f"Entidade ausente no pacote: {entity}")
        path = self.package_dir / filename
        expected_hash = self.manifest["files"][filename].get("sha256")
        if self.sha256(path) != expected_hash:
            raise CommandError(f"Hash inválido para o arquivo do pacote: {filename}")
        records = []
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError as exc:
            raise CommandError(f"Arquivo ausente no pacote: {path}") from exc
        for line_number, line in enumerate(lines, start=1):
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise CommandError(
                    f"JSON inválido em {filename}, linha {line_number}."
                ) from exc
            if not isinstance(record, dict) or (
                record.get("entity") != entity
                or not record.get("source", {}).get("id")
                or not isinstance(record.get("data"), dict)
            ):
                raise CommandError(
                    f"Registro inválido em {filename}, linha {line_number}."
                )
            records.append(record)
        expected_records = self.manifest["files"][filename].get("records")
        if expected_records != len(records):
            raise CommandError(
                f"Quantidade de registros divergente em {filename}."
            )
        return records

    @staticmethod
    def sha256(path: Path) -> str:
        digest = hashlib.sha256()
        try:
            with path.open("rb") as file:
                for block in iter(lambda: file.read(1024 * 1024), b""):
                    digest.update(block)
        except FileNotFoundError as exc:
            raise CommandError(f"Arquivo ausente no pacote: {path}") from exc
        return digest.hexdigest()


class Command(BaseCommand):
    help = "Aplica um pacote normalizado de dados legados no banco de produção."

    def add_arguments(self, parser):
        parser.add_argument(
            "--package-dir",
            default=os.getenv("SEED_PACKAGE_DIR", ""),
            help="Diretório do pacote normalizado (ou use SEED_PACKAGE_DIR).",
        )
        parser.add_argument(
            "--created-by-email",
            default=os.getenv("SEED_IMPORT_USER_EMAIL", "seed-import@localhost"),
            help="Usuário técnico usado em registros que exigem criado_por.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Valida e simula a importação sem persistir dados.",
        )

    def handle(self, *args, **options):
        package_dir = Path(options["package_dir"]).expanduser()
        if not options["package_dir"]:
            raise CommandError(
                "Informe --package-dir ou configure SEED_PACKAGE_DIR."
            )
        if not package_dir.is_dir():
            raise CommandError(f"Diretório de pacote não encontrado: {package_dir}")

        package = PackageReader(package_dir)
        self.counts = Counter()
        self.warnings: list[str] = []
        try:
            with transaction.atomic():
                technical_user = self.ensure_technical_user(
                    options["created_by_email"]
                )
                source_keys = self.import_package(package, technical_user)
                self.report_missing(source_keys, technical_user)
                self.report_package_issues(package)
                if options["dry_run"]:
                    raise DryRunRollback
        except DryRunRollback:
            self.stdout.write(
                self.style.WARNING("Dry-run concluído; nada foi persistido.")
            )

        self.stdout.write("\nResumo da importação:")
        for key, value in sorted(self.counts.items()):
            self.stdout.write(f"  {key}: {value}")
        for warning in self.warnings:
            self.stdout.write(self.style.WARNING(f"  Aviso: {warning}"))
        self.stdout.write(
            self.style.SUCCESS(
                "Seed de produção concluído."
                if not options["dry_run"]
                else "Seed de produção validado."
            )
        )

    def ensure_technical_user(self, email: str):
        user_model = get_user_model()
        user, created = user_model.objects.get_or_create(
            email=email,
            defaults={"nome": "Importação de dados legados", "ativo": True},
        )
        if created:
            user.set_unusable_password()
            user.save(update_fields=["password"])
            self.counts["users.created"] += 1
        return user

    def import_package(self, package: PackageReader, technical_user):
        source_keys = {}
        state_records = package.records("states")
        source_keys["states"] = self.import_states(state_records)
        territory_records = package.records("territories")
        territories = self.import_territories(territory_records)
        source_keys["territories"] = {
            (obj.nome, tuple(obj.estados)) for obj in territories.values()
        }
        municipality_records = package.records("municipalities")
        municipalities = self.import_municipalities(
            municipality_records, territories
        )
        source_keys["municipalities"] = set(municipalities)
        community_records = package.records("communities")
        self.import_communities(
            community_records, municipalities, technical_user
        )
        source_keys["communities"] = {
            (record["data"]["nome"], record["data"]["municipality_code"])
            for record in community_records
        }
        culture_records = package.records("cultures")
        source_keys["cultures"] = self.import_catalog(
            Cultura, culture_records, "cultures"
        )
        animal_records = package.records("animals")
        source_keys["animals"] = self.import_catalog(
            EspecieAnimal, animal_records, "animals"
        )
        people_records = package.records("people")
        source_keys["people"] = self.import_people(people_records)
        return source_keys

    def upsert(
        self,
        model,
        record: dict[str, Any],
        lookup: dict[str, Any],
        defaults: dict[str, Any],
    ):
        source = record["source"]
        content_type = ContentType.objects.get_for_model(model)
        mapping = SeedImportRecord.objects.filter(
            source_file=source["file"],
            source_sheet=source["sheet"],
            source_id=source["id"],
        ).first()
        obj = None
        if mapping and mapping.content_type_id == content_type.id:
            obj = model.objects.filter(pk=mapping.object_id).first()
        if obj is None:
            obj = (
                model.objects.select_for_update()
                .filter(**lookup)
                .order_by("pk")
                .first()
            )
            if obj is None:
                obj = model.objects.create(**lookup, **defaults)
                created = True
            else:
                for field, value in defaults.items():
                    setattr(obj, field, value)
                obj.save()
                created = False
        else:
            for field, value in {**lookup, **defaults}.items():
                setattr(obj, field, value)
            obj.save()
            created = False
        SeedImportRecord.objects.update_or_create(
            source_file=source["file"],
            source_sheet=source["sheet"],
            source_id=source["id"],
            defaults={
                "content_type": content_type,
                "object_id": obj.pk,
            },
        )
        return obj, created

    def import_states(self, records):
        source_states = set()
        for record in records:
            data = record["data"]
            source_states.add(data["sigla"])
            _, created = self.upsert(
                State,
                record,
                {"sigla": data["sigla"]},
                {"nome": data["nome"]},
            )
            self.counts[f"states.{'created' if created else 'updated'}"] += 1
        return source_states

    def import_territories(self, records):
        territories = {}
        for record in records:
            data = record["data"]
            states = sorted(data.get("estados", []))
            obj, created = self.upsert(
                Territory,
                record,
                {"nome": data["nome"]},
                {"estados": states, "ativo": True},
            )
            territories[record["source"]["id"]] = obj
            self.counts[
                f"territories.{'created' if created else 'updated'}"
            ] += 1
        return territories

    def import_municipalities(self, records, territories):
        municipalities = {}
        for record in records:
            data = record["data"]
            state = State.objects.filter(sigla=data["sigla_estado"]).first()
            if state is None:
                self.warnings.append(
                    f"Município {data['codigo_ibge']} referencia UF inexistente."
                )
                self.counts["municipalities.unmapped_state"] += 1
                continue
            territory = territories.get(data.get("territorio_id"))
            if data.get("territorio_id") and territory is None:
                self.counts["municipalities.unmapped_territory"] += 1
            defaults = {
                "nome": data["nome"],
                "state": state,
                "territory": territory,
            }
            for field in (
                "area_km2",
                "pop_total",
                "pop_rural",
                "idh",
                "perc_extr_pobres",
                "benef_programa_agri_familiar",
                "estab_agri_familiar",
            ):
                if field in data:
                    defaults[field] = data[field]
            obj, created = self.upsert(
                Municipality,
                record,
                {"codigo_ibge": data["codigo_ibge"]},
                defaults,
            )
            municipalities[data["codigo_ibge"]] = obj
            self.counts[
                f"municipalities.{'created' if created else 'updated'}"
            ] += 1
        return municipalities

    def import_communities(self, records, municipalities, technical_user):
        for record in records:
            data = record["data"]
            municipality = municipalities.get(data["municipality_code"])
            if municipality is None:
                self.counts["communities.unmapped_municipality"] += 1
                continue
            _, created = self.upsert(
                Comunidade,
                record,
                {"nome": data["nome"], "municipio": municipality},
                {
                    "lat": data.get("lat"),
                    "lng": data.get("lng"),
                    "ativa": True,
                    "criada_por": technical_user,
                },
            )
            self.counts[
                f"communities.{'created' if created else 'updated'}"
            ] += 1

    def import_catalog(self, model, records, entity):
        source_names = set()
        for record in records:
            data = record["data"]
            source_names.add(data["nome"])
            defaults = {
                "ativa": True,
                "categoria": data["categoria"],
            }
            if entity == "cultures":
                defaults["ciclo"] = data["ciclo"]
            _, created = self.upsert(
                model,
                record,
                {"nome": data["nome"]},
                defaults,
            )
            self.counts[f"{entity}.{'created' if created else 'updated'}"] += 1
        return source_names

    def import_people(self, records):
        source_emails = set()
        user_model = get_user_model()
        for record in records:
            data = record["data"]
            source_emails.add(data["email"])
            user, created = self.upsert(
                user_model,
                record,
                {"email": data["email"]},
                {
                    "nome": data["nome"],
                    "telefone": data.get("telefone", ""),
                    "ativo": True,
                },
            )
            if created:
                user.set_unusable_password()
                user.save(update_fields=["password"])
            self.counts[f"people.{'created' if created else 'updated'}"] += 1
        return source_emails

    def report_missing(self, source_keys, technical_user):
        missing = {
            "states": set(State.objects.values_list("sigla", flat=True))
            - source_keys["states"],
            "territories": {
                (obj.nome, tuple(obj.estados)) for obj in Territory.objects.all()
            }
            - source_keys["territories"],
            "municipalities": set(
                Municipality.objects.values_list("codigo_ibge", flat=True)
            )
            - source_keys["municipalities"],
            "communities": {
                (obj.nome, obj.municipio.codigo_ibge)
                for obj in Comunidade.objects.select_related("municipio")
            }
            - source_keys["communities"],
            "cultures": set(Cultura.objects.values_list("nome", flat=True))
            - source_keys["cultures"],
            "animals": set(EspecieAnimal.objects.values_list("nome", flat=True))
            - source_keys["animals"],
            "people": set(
                get_user_model()
                .objects.exclude(pk=technical_user.pk)
                .values_list("email", flat=True)
            )
            - source_keys["people"],
        }
        labels = {
            "states": "estados",
            "territories": "territórios",
            "municipalities": "municípios",
            "communities": "comunidades",
            "cultures": "culturas",
            "animals": "espécies",
            "people": "pessoas",
        }
        for key, values in missing.items():
            if not values:
                continue
            self.counts[f"{key}.missing"] = len(values)
            examples = ", ".join(sorted(map(str, values))[:10])
            self.warnings.append(
                f"{len(values)} {labels[key]} não aparecem no pacote "
                f"(exemplos: {examples})."
            )

    def report_package_issues(self, package: PackageReader):
        for issue in package.report.get("issues", []):
            if issue.get("type") == "unsupported_sheet":
                self.counts["sgp.sheets_not_supported"] += 1
            elif issue.get("type") == "duplicate":
                self.counts["people.duplicate_email"] += 1
        if package.report.get("issues"):
            self.warnings.append(
                "O relatório de preparação contém "
                f"{len(package.report['issues'])} ocorrência(s); consulte report.json."
            )
