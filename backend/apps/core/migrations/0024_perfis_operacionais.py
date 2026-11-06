from django.db import migrations, models
from django.db.models import Q

PERFIS_OPERACIONAIS = [
    ("coordenador-evento", "Coordenador de Evento"),
    ("credenciador", "Credenciador"),
    ("avaliador-selecao", "Avaliador de Seleção"),
    ("gestor-edital", "Gestor de Edital"),
]

# CHECK não enxerga outra tabela, e a categoria está em `core_role`.
TRIGGER_DA_ABRANGENCIA = """
CREATE OR REPLACE FUNCTION core_userprofile_validar_abrangencia() RETURNS trigger AS $$
DECLARE
    operacional boolean;
BEGIN
    SELECT categoria = 'operacional' INTO operacional FROM core_role WHERE id = NEW.perfil_id;
    IF NOT FOUND THEN
        RETURN NEW;
    END IF;
    IF operacional <> (NEW.objeto_tipo IS NOT NULL) OR (operacional AND NEW.territorio_id IS NOT NULL) THEN
        RAISE EXCEPTION 'Abrangência inválida para o perfil % do usuário %.', NEW.perfil_id, NEW.user_id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER core_userprofile_abrangencia
BEFORE INSERT OR UPDATE ON core_userprofile
FOR EACH ROW EXECUTE FUNCTION core_userprofile_validar_abrangencia();
"""

REMOVER_TRIGGER = """
DROP TRIGGER IF EXISTS core_userprofile_abrangencia ON core_userprofile;
DROP FUNCTION IF EXISTS core_userprofile_validar_abrangencia();
"""


def semear_perfis_operacionais(apps, schema_editor):
    Role = apps.get_model("core", "Role")
    for slug, nome in PERFIS_OPERACIONAIS:
        Role.objects.update_or_create(slug=slug, defaults={"nome": nome, "categoria": "operacional", "ativo": True})


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0023_seed_budget_limites"),
    ]

    operations = [
        migrations.AddField(
            model_name="role",
            name="categoria",
            field=models.CharField(
                choices=[("principal", "Principal"), ("operacional", "Operacional")],
                default="principal", max_length=15,
            ),
        ),
        migrations.AlterField(
            model_name="role",
            name="slug",
            field=models.SlugField(
                choices=[
                    ("agricultor", "Agricultor / Beneficiário"),
                    ("adt-acr", "ADT / ACR"),
                    ("articulador-estadual", "Articulador Estadual"),
                    ("ugp", "UGP — Coordenação"),
                    ("fgd", "FGD — Administrativo"),
                    ("super-admin", "Super Admin"),
                    ("coordenador-evento", "Coordenador de Evento"),
                    ("credenciador", "Credenciador"),
                    ("avaliador-selecao", "Avaliador de Seleção"),
                    ("gestor-edital", "Gestor de Edital"),
                ],
                unique=True,
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="objeto_tipo",
            field=models.CharField(
                blank=True,
                choices=[("evento", "Evento"), ("edital", "Edital"), ("candidatura", "Candidatura")],
                max_length=15, null=True, verbose_name="Tipo do objeto",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="objeto_id",
            field=models.PositiveBigIntegerField(
                blank=True,
                help_text="Referência sem FK: evento, edital ou candidatura designados ao perfil operacional.",
                null=True, verbose_name="ID do objeto",
            ),
        ),
        migrations.AddConstraint(
            model_name="userprofile",
            constraint=models.CheckConstraint(
                condition=(
                    Q(objeto_tipo__isnull=True, objeto_id__isnull=True)
                    | Q(objeto_tipo__isnull=False, objeto_id__isnull=False)
                ),
                name="ck_userprofile_objeto_tipo_e_id_juntos",
            ),
        ),
        migrations.RunPython(semear_perfis_operacionais, migrations.RunPython.noop),
        migrations.RunSQL(TRIGGER_DA_ABRANGENCIA, REMOVER_TRIGGER),
    ]
