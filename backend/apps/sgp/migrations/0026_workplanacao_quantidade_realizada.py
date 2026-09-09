from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sgp", "0025_migra_parceiros_para_organizacoes"),
    ]

    operations = [
        migrations.AddField(
            model_name="workplanacao",
            name="quantidade_realizada",
            field=models.PositiveIntegerField(
                default=0,
                help_text=(
                    "Materializado: conta Atividades com status='concluido' e ativo=True. "
                    "Atualizado por signal em apps.sgp.signals.workplan (issue #229) — "
                    "não editar diretamente; use `manage.py verificar_progresso_acoes` "
                    "para reconciliar em caso de divergência."
                ),
                verbose_name="Quantidade Realizada",
            ),
        ),
    ]
