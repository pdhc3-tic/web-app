import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0015_alter_auditlog_and_notification"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="acesso_revogado",
            field=models.BooleanField(
                default=False,
                help_text="Se True, o app SCA apaga os dados locais e exige novo login (wipe remoto).",
                verbose_name="Acesso revogado",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="acesso_revogado_em",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Revogado em"),
        ),
        migrations.AddField(
            model_name="user",
            name="acesso_revogado_por",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="revogacoes_realizadas",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Revogado por",
            ),
        ),
    ]
