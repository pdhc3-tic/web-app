import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def backfill_iniciado_em(apps, schema_editor):
    """Eventos legados não têm início registrado: assume-se = finalizado_em,
    evitando NULLS FIRST na ordenação padrão -iniciado_em."""
    from django.db.models import F

    SyncEvent = apps.get_model("sca", "SyncEvent")
    SyncEvent.objects.filter(iniciado_em__isnull=True).update(iniciado_em=F("finalizado_em"))


class Migration(migrations.Migration):

    dependencies = [
        ("sca", "0001_initial"),
        ("core", "0017_merge_20260804_1648"),
    ]

    operations = [
        # SyncEvent updates
        migrations.RemoveIndex(
            model_name="syncevent",
            name="idx_sca_event_user_rec",
        ),
        migrations.RenameField(
            model_name="syncevent",
            old_name="recebido_em",
            new_name="finalizado_em",
        ),
        migrations.AddField(
            model_name="syncevent",
            name="iniciado_em",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Iniciado em"),
        ),
        migrations.RunPython(
            backfill_iniciado_em,
            migrations.RunPython.noop,
        ),
        migrations.AddField(
            model_name="syncevent",
            name="contagem_enviados",
            field=models.PositiveIntegerField(default=0, verbose_name="Contagem enviados"),
        ),
        migrations.AddField(
            model_name="syncevent",
            name="contagem_recebidos",
            field=models.PositiveIntegerField(default=0, verbose_name="Contagem recebidos"),
        ),
        migrations.AddField(
            model_name="syncevent",
            name="contagem_erros",
            field=models.PositiveIntegerField(default=0, verbose_name="Contagem erros"),
        ),
        migrations.AddField(
            model_name="syncevent",
            name="erros_detalhes",
            field=models.JSONField(blank=True, default=list, verbose_name="Detalhes dos erros"),
        ),
        migrations.AddField(
            model_name="syncevent",
            name="tipo_conexao",
            field=models.CharField(
                blank=True,
                choices=[
                    ("wifi", "Wi-Fi"),
                    ("4g", "4G"),
                    ("3g", "3G"),
                    ("2g", "2G"),
                    ("5g", "5G"),
                    ("offline", "Offline"),
                ],
                max_length=20,
                null=True,
                verbose_name="Tipo de conexão",
            ),
        ),
        migrations.AlterModelOptions(
            name="syncevent",
            options={
                "ordering": ["-iniciado_em", "-finalizado_em"],
                "verbose_name": "Evento de Sincronização",
                "verbose_name_plural": "Eventos de Sincronização",
            },
        ),
        migrations.AddIndex(
            model_name="syncevent",
            index=models.Index(fields=["device", "-iniciado_em"], name="idx_sca_event_device_ini"),
        ),
        migrations.AddIndex(
            model_name="syncevent",
            index=models.Index(fields=["user", "-finalizado_em"], name="idx_sca_event_user_rec"),
        ),

        # ConflictLog updates
        migrations.AddField(
            model_name="conflictlog",
            name="status",
            field=models.CharField(
                choices=[
                    ("pendente", "Pendente"),
                    ("resolvido_auto", "Resolvido Automaticamente"),
                    ("resolvido_manual", "Resolvido Manualmente"),
                ],
                default="resolvido_auto",
                max_length=20,
                verbose_name="Status de resolução",
            ),
        ),
        migrations.AddField(
            model_name="conflictlog",
            name="valor_final",
            field=models.JSONField(blank=True, null=True, verbose_name="Valor final aplicado"),
        ),
        migrations.AddField(
            model_name="conflictlog",
            name="resolvido_por",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="sca_conflicts_resolved",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Resolvido por",
            ),
        ),
        migrations.AddField(
            model_name="conflictlog",
            name="resolvido_em",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Resolvido em"),
        ),
        migrations.AddField(
            model_name="conflictlog",
            name="territorio",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="sca_conflicts",
                to="core.territory",
                verbose_name="Território",
            ),
        ),
        migrations.AddIndex(
            model_name="conflictlog",
            index=models.Index(fields=["status", "campo_sensivel"], name="idx_sca_conflict_status"),
        ),
    ]
