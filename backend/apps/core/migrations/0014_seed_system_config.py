from django.db import migrations


SEED_CONFIGS = [
    {"chave": "session_timeout_hours",         "valor": "8",     "tipo": "integer", "descricao": "Tempo limite da sessão em horas"},
    {"chave": "max_login_attempts",            "valor": "5",     "tipo": "integer", "descricao": "Máximo de tentativas de login"},
    {"chave": "lockout_minutes",               "valor": "30",    "tipo": "integer", "descricao": "Tempo de bloqueio após tentativas"},
    {"chave": "notification_demand_alert_days","valor": "30",    "tipo": "integer", "descricao": "Dias para alerta de demanda"},
    {"chave": "notification_form_deadline_days","valor": "15",   "tipo": "integer", "descricao": "Dias para prazo de formulário"},
    {"chave": "user_inactive_alert_days",      "valor": "90",    "tipo": "integer", "descricao": "Dias para alerta de usuário inativo"},
    {"chave": "backup_retention_days",         "valor": "30",    "tipo": "integer", "descricao": "Dias de retenção de backup"},
    {"chave": "sca_sync_batch_limit",          "valor": "100",   "tipo": "integer", "descricao": "Limite de lote de sincronização SCA"},
    {"chave": "report_export_row_limit",       "valor": "10000", "tipo": "integer", "descricao": "Limite de linhas exportadas"},
]


def seed_system_config(apps, schema_editor):
    SystemConfig = apps.get_model("core", "SystemConfig")
    for cfg in SEED_CONFIGS:
        SystemConfig.objects.get_or_create(chave=cfg["chave"], defaults=cfg)


def reverse_seed(apps, schema_editor):
    SystemConfig = apps.get_model("core", "SystemConfig")
    SystemConfig.objects.filter(
        chave__in=[c["chave"] for c in SEED_CONFIGS]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0013_alter_auditlog_acao_alter_auditlog_entidade_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_system_config, reverse_seed),
    ]
