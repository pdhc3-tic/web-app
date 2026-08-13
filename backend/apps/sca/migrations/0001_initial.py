import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0015_alter_auditlog_and_notification"),
    ]

    operations = [
        migrations.CreateModel(
            name="SyncDevice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("device_id", models.CharField(max_length=100, verbose_name="Device ID")),
                ("nome", models.CharField(blank=True, default="", max_length=255, verbose_name="Nome do dispositivo")),
                ("modelo", models.CharField(blank=True, default="", max_length=100, verbose_name="Modelo")),
                ("sistema_operacional", models.CharField(blank=True, default="", max_length=50, verbose_name="Sistema operacional")),
                ("app_versao", models.CharField(blank=True, default="", max_length=20, verbose_name="Versão do app")),
                ("ultimo_push_em", models.DateTimeField(blank=True, null=True, verbose_name="Último push")),
                ("ultimo_pull_em", models.DateTimeField(blank=True, null=True, verbose_name="Último pull")),
                ("ultimo_refresh_em", models.DateTimeField(blank=True, null=True, verbose_name="Último refresh")),
                ("ativo", models.BooleanField(default=True, verbose_name="Ativo")),
                ("criado_em", models.DateTimeField(auto_now_add=True, verbose_name="Criado em")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sca_devices", to=settings.AUTH_USER_MODEL, verbose_name="Usuário")),
            ],
            options={
                "verbose_name": "Dispositivo SCA",
                "verbose_name_plural": "Dispositivos SCA",
                "ordering": ["-criado_em"],
            },
        ),
        migrations.CreateModel(
            name="ConflictLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("entidade", models.CharField(max_length=50, verbose_name="Entidade")),
                ("uuid_local", models.UUIDField(verbose_name="UUID local")),
                ("campo", models.CharField(max_length=255, verbose_name="Campo em conflito")),
                ("valor_local", models.JSONField(default=dict, verbose_name="Valor local (offline)")),
                ("valor_servidor", models.JSONField(default=dict, verbose_name="Valor no servidor")),
                ("estrategia", models.CharField(choices=[("last_write_wins", "Last-write-wins"), ("duplicate_rejeitado", "Duplicata rejeitada"), ("exclusao_prevalece", "Exclusão do servidor prevalece"), ("merge_automatico", "Merge automático")], default="last_write_wins", max_length=30, verbose_name="Estratégia aplicada")),
                ("campo_sensivel", models.BooleanField(default=False, verbose_name="Campo sensível")),
                ("criado_em", models.DateTimeField(auto_now_add=True, verbose_name="Criado em")),
                ("device", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="conflicts", to="sca.syncdevice", verbose_name="Dispositivo")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sca_conflicts", to=settings.AUTH_USER_MODEL, verbose_name="Usuário")),
            ],
            options={
                "verbose_name": "Log de Conflito",
                "verbose_name_plural": "Logs de Conflito",
                "ordering": ["-criado_em"],
            },
        ),
        migrations.CreateModel(
            name="SyncEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tipo", models.CharField(choices=[("push", "Push"), ("pull", "Pull"), ("refresh", "Refresh")], max_length=10, verbose_name="Tipo")),
                ("since", models.DateTimeField(blank=True, null=True, verbose_name="Since (pull)")),
                ("contagem", models.PositiveIntegerField(default=0, verbose_name="Registros processados")),
                ("recebido_em", models.DateTimeField(auto_now_add=True, verbose_name="Recebido em")),
                ("device", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sync_events", to="sca.syncdevice", verbose_name="Dispositivo")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sca_sync_events", to=settings.AUTH_USER_MODEL, verbose_name="Usuário")),
            ],
            options={
                "verbose_name": "Evento de Sincronização",
                "verbose_name_plural": "Eventos de Sincronização",
                "ordering": ["-recebido_em"],
            },
        ),
        migrations.AddIndex(
            model_name="syncdevice",
            index=models.Index(fields=["user", "ativo"], name="idx_sca_device_user_ativo"),
        ),
        migrations.AddConstraint(
            model_name="syncdevice",
            constraint=models.UniqueConstraint(fields=("user", "device_id"), name="uniq_sca_device_user_device"),
        ),
        migrations.AddIndex(
            model_name="syncevent",
            index=models.Index(fields=["user", "-recebido_em"], name="idx_sca_event_user_rec"),
        ),
        migrations.AddIndex(
            model_name="conflictlog",
            index=models.Index(fields=["user", "-criado_em"], name="idx_sca_conflict_user"),
        ),
        migrations.AddIndex(
            model_name="conflictlog",
            index=models.Index(fields=["uuid_local"], name="idx_sca_conflict_uuid"),
        ),
    ]
