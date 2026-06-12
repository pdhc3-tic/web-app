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
    territorios=None,
    password: str | None = None,
    role=None,
    **fields,
) -> "User":
    """
    Cria e salva um novo User, configurando senha e territórios.

    Args:
        territorios: lista/queryset de Territory para vincular via M2M.
        password: senha em texto plano (será hasheada via set_password).
        role: instância de Role (opcional).
        **fields: demais campos escalares do modelo User.
    """
    from apps.core.models import User as UserModel

    user = UserModel(**fields)
    if password:
        user.set_password(password)
    if role is not None:
        user.role = role
    user.save()
    if territorios:
        user.territorios.set(territorios)
    return user


def update_user(
    instance: "User",
    *,
    territorios=None,
    password: str | None = None,
    role=None,
    **fields,
) -> "User":
    """
    Atualiza os dados de um User existente.

    Args:
        instance: instância User a ser atualizada.
        territorios: nova lista de Territory (None = não altera; [] = limpa).
        password: nova senha em texto plano (None = não altera).
        role: novo Role (None = não altera).
        **fields: demais campos escalares a sobrescrever.
    """
    for attr, value in fields.items():
        setattr(instance, attr, value)

    if password:
        instance.set_password(password)
    if role is not None:
        instance.role = role

    instance.save()

    if territorios is not None:
        instance.territorios.set(territorios)

    return instance
