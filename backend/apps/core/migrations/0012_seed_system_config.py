from django.db import migrations


SEEDS = [
    ("session_timeout_hours", "8", "integer", "Tempo máximo de sessão em horas"),
    ("max_login_attempts", "5", "integer", "Número máximo de tentativas de login"),
    ("lockout_minutes", "15", "integer", "Tempo de bloqueio após tentativas excedidas em minutos"),
    ("notification_demand_alert_days", "5", "integer", "Dias de antecedência para alerta de demanda"),
    ("notification_form_deadline_days", "7", "integer", "Dias de antecedência para prazo de formulário"),
    ("user_inactive_alert_days", "30", "integer", "Dias de inatividade para alerta de usuário"),
    ("backup_retention_days", "90", "integer", "Dias de retenção de backups"),
    ("sca_sync_batch_limit", "100", "integer", "Limite de lotes para sincronização SCA"),
    ("report_export_row_limit", "50000", "integer", "Limite de linhas para exportação de relatórios"),
]


def seed_system_config(apps, schema_editor):
    SystemConfig = apps.get_model("core", "SystemConfig")
    for chave, valor, tipo, descricao in SEEDS:
        SystemConfig.objects.get_or_create(
            chave=chave,
            defaults={"valor": valor, "tipo": tipo, "descricao": descricao},
        )


def reverse_seed(apps, schema_editor):
    SystemConfig = apps.get_model("core", "SystemConfig")
    SystemConfig.objects.filter(chave__in=[s[0] for s in SEEDS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0011_systemconfig"),
    ]

    operations = [
        migrations.RunPython(seed_system_config, reverse_seed),
    ]
