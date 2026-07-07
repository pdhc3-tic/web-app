"""
Unifica UserProfile como única fonte de verdade para perfis e territórios.

- UserProfile.user: OneToOneField → ForeignKey (M:N User ↔ Role)
- Remove User.role (FK) e User.territorios (M2M)
- Data migration: copia User.role + User.territorios para UserProfile
"""
from django.db import migrations, models
import django.db.models.deletion


def forwards_copy_user_role_to_profile(apps, schema_editor):
    User = apps.get_model("core", "User")
    UserProfile = apps.get_model("core", "UserProfile")
    for user in User.objects.iterator():
        role_id = user.role_id
        if role_id is None:
            continue
        territorios = list(user.territorios.values_list("id", flat=True))
        if not territorios:
            UserProfile.objects.get_or_create(
                user=user,
                perfil_id=role_id,
                defaults={"territorio": None},
            )
        else:
            for t_id in territorios:
                UserProfile.objects.get_or_create(
                    user=user,
                    perfil_id=role_id,
                    territorio_id=t_id,
                )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0014_seed_system_config"),
    ]

    operations = [
        migrations.AlterField(
            model_name="userprofile",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="profiles",
                to="core.user",
            ),
        ),
        migrations.RunPython(forwards_copy_user_role_to_profile, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="user",
            name="role",
        ),
        migrations.RemoveField(
            model_name="user",
            name="territorios",
        ),
        migrations.AlterModelOptions(
            name="user",
            options={
                "ordering": ["email"],
                "verbose_name": "Usuario",
                "verbose_name_plural": "Users",
            },
        ),
    ]
