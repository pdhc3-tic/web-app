from django.core.management.base import BaseCommand
import csv

from core.models import Role, State, Territory, Municipality
from django.conf import settings


ROLES = [
    ("agricultor", "Agricultor / Beneficiário"),
    ("adt-acr", "ADT / ACR"),
    ("articulador-estadual", "Articulador Estadual"),
    ("ugp", "UGP — Coordenação"),
    ("fgd", "FGD — Administrativo"),
    ("super-admin", "Super Admin"),
]

STATES = ["PE", "PB", "AL", "RN", "MA", "BA", "MG"]

# Minimal placeholder territories: one per state

def ensure_roles(stdout):
    for slug, nome in ROLES:
        role, created = Role.objects.get_or_create(slug=slug, defaults={"nome": nome, "ativo": True})
        if not created:
            # ensure name is up to date
            if role.nome != nome:
                role.nome = nome
                role.save()
        stdout.write(f"Role: {slug} -> {'created' if created else 'exists'}")


def ensure_states(stdout):
    for sigla in STATES:
        state, created = State.objects.get_or_create(sigla=sigla, defaults={"nome": sigla})
        stdout.write(f"State: {sigla} -> {'created' if created else 'exists'}")


def ensure_territories(stdout):
    # Create at least one territory per state
    for sigla in STATES:
        name = f"Território {sigla}"
        territory, created = Territory.objects.get_or_create(nome=name, defaults={"estados": [sigla], "ativo": True})
        if not created and sigla not in territory.estados:
            territory.estados = list(set(territory.estados) | {sigla})
            territory.save()
        stdout.write(f"Territory: {name} -> {'created' if created else 'exists'}")


def ensure_sample_municipalities(stdout):
    # Create a small sample of municipalities (one per state) for tests/dev
    counter = 1
    for sigla in STATES:
        state = State.objects.get(sigla=sigla)
        codigo = f"{counter:07d}"
        nome = f"Município Exemplo {sigla}"
        territory = Territory.objects.filter(estados__contains=[sigla]).first()
        obj, created = Municipality.objects.get_or_create(codigo_ibge=codigo, defaults={
            "nome": nome,
            "state": state,
            "territory": territory,
        })
        if not created:
            updated = False
            if obj.nome != nome:
                obj.nome = nome
                updated = True
            if obj.state != state:
                obj.state = state
                updated = True
            if obj.territory != territory:
                obj.territory = territory
                updated = True
            if updated:
                obj.save()
        stdout.write(f"Municipality: {codigo} ({sigla}) -> {'created' if created else 'exists/updated'}")
        counter += 1


class Command(BaseCommand):
    help = "Seed core data (roles, states, territories, sample municipalities)."

    def add_arguments(self, parser):
        parser.add_argument("--from-csv", dest="csvfile", help="Import municipalities from an IBGE CSV file")

    def handle(self, *args, **options):
        stdout = self.stdout
        self.stdout.write("Seeding core data...")

        ensure_roles(stdout)
        ensure_states(stdout)
        ensure_territories(stdout)

        csvfile = options.get("csvfile")
        if csvfile:
            # Import from CSV: expected columns: codigo_ibge,nome,sigla,...
            self.stdout.write(f"Importing municipalities from {csvfile}...")
            with open(csvfile, newline='', encoding='utf-8') as fh:
                reader = csv.DictReader(fh)
                created = 0
                for row in reader:
                    sigla = row.get('sigla') or row.get('uf')
                    if not sigla:
                        continue
                    state, _ = State.objects.get_or_create(sigla=sigla, defaults={"nome": sigla})
                    territory_name = row.get('territory') or f"Território {sigla}"
                    territory, _ = Territory.objects.get_or_create(nome=territory_name, defaults={"estados": [sigla], "ativo": True})
                    codigo = row.get('codigo_ibge') or row.get('cod_ibge')
                    if not codigo:
                        continue
                    mun, mun_created = Municipality.objects.update_or_create(
                        codigo_ibge=codigo,
                        defaults={
                            'nome': row.get('nome') or row.get('municipio'),
                            'state': state,
                            'territory': territory,
                            'area_km2': row.get('area_km2') or None,
                            'pop_total': row.get('pop_total') or None,
                            'pop_rural': row.get('pop_rural') or None,
                            'idh': row.get('idh') or None,
                            'perc_extr_pobres': row.get('perc_extr_pobres') or None,
                            'benef_programa_agri_familiar': row.get('benef_programa_agri_familiar') or None,
                            'estab_agri_familiar': row.get('estab_agri_familiar') or None,
                        }
                    )
                    if mun_created:
                        created += 1
                self.stdout.write(f"Imported {created} municipalities from CSV.")
        else:
            ensure_sample_municipalities(stdout)

        self.stdout.write(self.style.SUCCESS("Seeding complete."))
