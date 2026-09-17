"""
Cria um Tecnico para cada usuário com perfil adt-acr ou articulador-estadual,
herdando o território do UserProfile (issue #225).

Como Tecnico.user é OneToOneField, um usuário com múltiplos UserProfile
qualificados (mesmo papel ou papéis diferentes, em territórios distintos)
gera um único Tecnico: prioriza-se o primeiro UserProfile encontrado (por
id), trocando o candidato somente se o atual tiver território nulo (acesso
global) e um perfil mais específico (com território) for encontrado depois.
"""
from django.db import migrations

PAPEIS_TECNICOS = ["adt-acr", "articulador-estadual"]


def cria_tecnicos_para_perfis_existentes(apps, schema_editor):
    UserProfile = apps.get_model("core", "UserProfile")
    Tecnico = apps.get_model("sgp", "Tecnico")

    candidatos = {}
    perfis = (
        UserProfile.objects.filter(perfil__slug__in=PAPEIS_TECNICOS)
        .select_related("perfil")
        .order_by("id")
    )
    for perfil_usuario in perfis:
        atual = candidatos.get(perfil_usuario.user_id)
        if atual is None or (
            atual.territorio_id is None and perfil_usuario.territorio_id is not None
        ):
            candidatos[perfil_usuario.user_id] = perfil_usuario

    for user_id, perfil_usuario in candidatos.items():
        Tecnico.objects.get_or_create(
            user_id=user_id,
            defaults={
                "territorio_id": perfil_usuario.territorio_id,
                "papel": perfil_usuario.perfil.slug,
                "ativo": True,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("sgp", "0018_tecnico"),
    ]

    operations = [
        migrations.RunPython(
            cria_tecnicos_para_perfis_existentes, migrations.RunPython.noop
        ),
    ]
