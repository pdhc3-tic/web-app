from django.db import migrations


GOOGLE_CALENDAR_CONFIGS = [
    {
        "chave": "google_calendar_calendario_destino_id",
        "valor": "",
        "tipo": "string",
        "descricao": "ID do calendário destino da integração Google Calendar.",
    },
    {
        "chave": "google_calendar_lembretes",
        "valor": "[1440, 60]",
        "tipo": "json",
        "descricao": "Lembretes da integração Google Calendar em minutos antes do evento.",
    },
    {
        "chave": "google_calendar_integracao_ativa",
        "valor": "False",
        "tipo": "boolean",
        "descricao": "Indica se novas sincronizações com Google Calendar estão ativas.",
    },
]


def seed_google_calendar_config(apps, schema_editor):
    SystemConfig = apps.get_model("core", "SystemConfig")
    for config in GOOGLE_CALENDAR_CONFIGS:
        SystemConfig.objects.get_or_create(
            chave=config["chave"],
            defaults=config,
        )


def reverse_google_calendar_config(apps, schema_editor):
    SystemConfig = apps.get_model("core", "SystemConfig")
    SystemConfig.objects.filter(
        chave__in=[config["chave"] for config in GOOGLE_CALENDAR_CONFIGS]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("core", "0015_alter_auditlog_and_notification")]

    operations = [
        migrations.RunPython(
            seed_google_calendar_config,
            reverse_google_calendar_config,
        ),
    ]
