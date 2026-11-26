"""Confere se todo campo criptografado do banco decifra com a FIELD_ENCRYPTION_KEY atual.

É a prova de que dump + chave restauram o dado sensível (saúde, cor/raça, CPF
de beneficiário...): roda no ensaio de restauração e depois de trazer um banco
de outra máquina. Lê a coluna crua (sem o ORM decifrar) e imprime só contagens,
nunca valores. Sai com erro se alguma linha não decifrar.

Uso, com o env de runtime:
    python manage.py verificar_criptografia
"""
from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from apps.core.crypto import decrypt_to_text
from apps.core.fields import EncryptedFieldMixin


class Command(BaseCommand):
    help = "Conta, por coluna criptografada, quantos valores decifram com a chave atual."

    def handle(self, *args, **options):
        falhas = 0
        quote = connection.ops.quote_name
        for model in apps.get_models():
            colunas = [f.column for f in model._meta.concrete_fields if isinstance(f, EncryptedFieldMixin)]
            if not colunas:
                continue
            tabela = model._meta.db_table
            with connection.cursor() as cursor:
                cursor.execute("SELECT relrowsecurity FROM pg_class WHERE oid = %s::regclass", [tabela])
                if cursor.fetchone()[0]:
                    raise CommandError(f"{tabela} tem RLS: a contagem como runtime sairia incompleta.")
                # ponytail: lê a tabela inteira de uma vez; vira cursor nomeado se passar de centenas de mil linhas.
                cursor.execute(f"SELECT {', '.join(quote(c) for c in colunas)} FROM {quote(tabela)}")
                linhas = cursor.fetchall()
            for i, coluna in enumerate(colunas):
                valores = [linha[i] for linha in linhas if linha[i] not in (None, "")]
                ruins = 0
                for valor in valores:
                    try:
                        decrypt_to_text(valor)
                    except ValueError:
                        ruins += 1
                falhas += ruins
                self.stdout.write(f"{tabela}.{coluna}: {len(valores) - ruins}/{len(valores)} decifram")
        if falhas:
            raise CommandError(f"{falhas} valor(es) não decifram com a FIELD_ENCRYPTION_KEY atual.")
        self.stdout.write(self.style.SUCCESS("Todos os valores criptografados decifram."))
