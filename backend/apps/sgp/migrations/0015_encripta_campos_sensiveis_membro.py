# Issue #187 — Proteção de campos sensíveis (Saúde, Cor/Raça).
#
# Não usamos um simples `AlterField`: o cast automático que o Postgres faria
# (smallint/jsonb -> text) apenas converteria o valor existente para texto
# plano — ele continuaria legível, e ainda quebraria a leitura seguinte
# (from_db_value tentaria decriptar um valor que nunca foi criptografado).
#
# Estratégia segura, em 4 passos, para preservar dados já existentes:
#   1. Adiciona colunas temporárias já com os campos criptografados.
#   2. RunPython: para cada membro, atribui o valor antigo (ainda em texto
#      claro) ao campo novo e salva — a criptografia acontece de forma
#      transparente via `EncryptedFieldMixin.get_prep_value`.
#   3. Remove as colunas antigas (texto claro).
#   4. Renomeia as colunas temporárias para os nomes originais.
import apps.core.fields
from django.db import migrations


def encripta_campos_sensiveis(apps, schema_editor):
    MembroFamilia = apps.get_model("sgp", "MembroFamilia")
    membros = MembroFamilia.objects.only(
        "id", "cor_raca", "saude", "cor_raca_enc", "saude_enc"
    ).iterator(chunk_size=500)
    for membro in membros:
        membro.cor_raca_enc = membro.cor_raca
        membro.saude_enc = membro.saude if membro.saude is not None else []
        membro.save(update_fields=["cor_raca_enc", "saude_enc"])


class Migration(migrations.Migration):

    dependencies = [
        ('sgp', '0014_merge_20260828_1500'),
    ]

    operations = [
        migrations.AddField(
            model_name='membrofamilia',
            name='cor_raca_enc',
            field=apps.core.fields.EncryptedIntChoiceField(
                blank=True,
                choices=[(1, 'Branca'), (2, 'Preta'), (3, 'Parda'), (4, 'Amarela'), (5, 'Indígena')],
                help_text='Armazenado criptografado em repouso (AES-256-GCM). Leitura restrita por perfil — ver apps.core.sensitive_fields.',
                null=True,
                verbose_name='Cor/Raça',
            ),
        ),
        migrations.AddField(
            model_name='membrofamilia',
            name='saude_enc',
            field=apps.core.fields.EncryptedJSONField(
                blank=True,
                default=list,
                help_text='Armazenado criptografado em repouso (AES-256-GCM). Leitura restrita por perfil — ver apps.core.sensitive_fields.',
                verbose_name='Condições de Saúde',
            ),
        ),
        migrations.RunPython(encripta_campos_sensiveis, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='membrofamilia',
            name='cor_raca',
        ),
        migrations.RemoveField(
            model_name='membrofamilia',
            name='saude',
        ),
        migrations.RenameField(
            model_name='membrofamilia',
            old_name='cor_raca_enc',
            new_name='cor_raca',
        ),
        migrations.RenameField(
            model_name='membrofamilia',
            old_name='saude_enc',
            new_name='saude',
        ),
    ]
