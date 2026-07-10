"""
Seed de dados de referência do SGP (Projetos).

Decisão CI/testes
-----------------
- Este comando é executado APENAS em ambientes de desenvolvimento e staging
  para popular o banco com dados reais de referência.
- Em testes automatizados (CI), NÃO usar este seed. Usar factory_boy
  (factories em apps/core/tests/factories.py) para criar fixtures isoladas
  por teste, garantindo velocidade e independência entre casos de teste.
"""
from django.core.management.base import BaseCommand
from apps.sgp.models import Projeto

PROJETOS = [
    {
        "nome": "Projeto Dom Hélder Câmara III",
        "descricao": "Projeto PDHC III",
        "ativo": True,
    },
]


class Command(BaseCommand):
    help = "Seed SGP data (projetos)."

    def handle(self, *args, **options):
        self.stdout.write("Seeding SGP data...")

        for item in PROJETOS:
            projeto, created = Projeto.objects.update_or_create(
                nome=item["nome"],
                defaults={
                    "descricao": item["descricao"],
                    "ativo": item["ativo"],
                },
            )
            self.stdout.write(
                f"Projeto: {projeto.nome} -> {'created' if created else 'updated'}"
            )

        self.stdout.write(self.style.SUCCESS("Seeding SGP complete."))