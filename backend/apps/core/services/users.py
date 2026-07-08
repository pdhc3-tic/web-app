"""
Service de usuários — lógica de criação e atualização de User.

Separado do serializer para que outros contextos (admin, shell, Celery)
possam criar/atualizar usuários sem depender do ciclo DRF.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.core.models import User


def create_user(
    *,
    password: str | None = None,
    perfis_input: list[dict] | None = None,
    **fields,
) -> "User":
    """
    Cria e salva um novo User, configurando senha e perfis (UserProfile).

    Args:
        password: senha em texto plano (será hasheada via set_password).
        perfis_input: lista de dicts com perfil_id e (opcional) territorio_id.
        **fields: demais campos escalares do modelo User.
    """
    from apps.core.models import User as UserModel
    from apps.core.models.user_profile import UserProfile

    user = UserModel(**fields)
    if password:
        user.set_password(password)
    user.save()

    if perfis_input:
        for item in perfis_input:
            UserProfile.objects.create(
                user=user,
                perfil_id=item["perfil_id"],
                territorio_id=item.get("territorio_id"),
            )

    return user


def update_user(
    instance: "User",
    *,
    password: str | None = None,
    perfis_input: list[dict] | None = None,
    **fields,
) -> "User":
    """
    Atualiza os dados de um User existente.

    Args:
        instance: instância User a ser atualizada.
        password: nova senha em texto plano (None = não altera).
        perfis_input: nova lista de perfis (None = não altera).
        **fields: demais campos escalares a sobrescrever.
    """
    from apps.core.models.user_profile import UserProfile

    for attr, value in fields.items():
        setattr(instance, attr, value)

    if password:
        instance.set_password(password)

    instance.save()

    if perfis_input is not None:
        instance.profiles.all().delete()
        for item in perfis_input:
            UserProfile.objects.create(
                user=instance,
                perfil_id=item["perfil_id"],
                territorio_id=item.get("territorio_id"),
            )

    return instance
