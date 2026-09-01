# Coluna nova + RunPython + remoção da antiga + rename, em vez de um simples
# AlterField: o ALTER COLUMN automático só converteria o JSON existente para
# texto plano, sem criptografar (mesma estratégia da migration 0015).
import apps.core.fields
from django.db import migrations


def encripta_valores_conflict_log(apps, schema_editor):
    ConflictLog = apps.get_model("sca", "ConflictLog")
    conflitos = ConflictLog.objects.only(
        "id", "valor_local", "valor_servidor", "valor_final",
        "valor_local_enc", "valor_servidor_enc", "valor_final_enc",
    ).iterator(chunk_size=500)
    for conflito in conflitos:
        conflito.valor_local_enc = conflito.valor_local
        conflito.valor_servidor_enc = conflito.valor_servidor
        conflito.valor_final_enc = conflito.valor_final
        conflito.save(
            update_fields=["valor_local_enc", "valor_servidor_enc", "valor_final_enc"]
        )


class Migration(migrations.Migration):

    dependencies = [
        ('sca', '0003_alter_syncevent_finalizado_em'),
    ]

    operations = [
        migrations.AddField(
            model_name='conflictlog',
            name='valor_local_enc',
            field=apps.core.fields.EncryptedJSONField(
                default=dict,
                help_text='Armazenado criptografado em repouso (AES-256-GCM) — pode conter campo sensível (saúde, cor/raça). Leitura restrita por perfil — ver apps.core.sensitive_fields.',
                verbose_name='Valor local (offline)',
            ),
        ),
        migrations.AddField(
            model_name='conflictlog',
            name='valor_servidor_enc',
            field=apps.core.fields.EncryptedJSONField(
                default=dict,
                help_text='Armazenado criptografado em repouso (AES-256-GCM) — pode conter campo sensível (saúde, cor/raça). Leitura restrita por perfil — ver apps.core.sensitive_fields.',
                verbose_name='Valor no servidor',
            ),
        ),
        migrations.AddField(
            model_name='conflictlog',
            name='valor_final_enc',
            field=apps.core.fields.EncryptedJSONField(
                blank=True,
                help_text='Armazenado criptografado em repouso (AES-256-GCM) — pode conter campo sensível (saúde, cor/raça). Leitura restrita por perfil — ver apps.core.sensitive_fields.',
                null=True,
                verbose_name='Valor final aplicado',
            ),
        ),
        migrations.RunPython(encripta_valores_conflict_log, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='conflictlog',
            name='valor_local',
        ),
        migrations.RemoveField(
            model_name='conflictlog',
            name='valor_servidor',
        ),
        migrations.RemoveField(
            model_name='conflictlog',
            name='valor_final',
        ),
        migrations.RenameField(
            model_name='conflictlog',
            old_name='valor_local_enc',
            new_name='valor_local',
        ),
        migrations.RenameField(
            model_name='conflictlog',
            old_name='valor_servidor_enc',
            new_name='valor_servidor',
        ),
        migrations.RenameField(
            model_name='conflictlog',
            old_name='valor_final_enc',
            new_name='valor_final',
        ),
    ]
