import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Cria o superusuário inicial sem alterar um superusuário existente."

    def add_arguments(self, parser):
        parser.add_argument("--email", default=os.getenv("SUPERUSER_EMAIL", ""))
        parser.add_argument("--name", default=os.getenv("SUPERUSER_NAME", ""))
        parser.add_argument(
            "--password", default=os.getenv("SUPERUSER_PASSWORD", "")
        )

    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        name = options["name"].strip()
        password = options["password"]
        if not email or not name or not password:
            raise CommandError(
                "Configure SUPERUSER_EMAIL, SUPERUSER_NAME e SUPERUSER_PASSWORD."
            )

        user_model = get_user_model()
        user = user_model.objects.filter(email=email).first()
        if user is not None:
            if not user.is_superuser:
                raise CommandError(
                    f"Já existe um usuário não administrador com o e-mail {email}."
                )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Superusuário {email} já existe; senha preservada."
                )
            )
            return

        user = user_model.objects.create_user(
            email=email,
            nome=name,
            password=password,
        )
        user.is_superuser = True
        user.ativo = True
        user.save(update_fields=["is_superuser", "ativo"])
        self.stdout.write(
            self.style.SUCCESS(f"Superusuário {email} criado com sucesso.")
        )
