"""
Classes de permissão RBAC — composable via & / | (DRF 3.9+).
Negações registradas com logger.warning para auditoria.
"""

from __future__ import annotations

import logging
from typing import Any

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.core.services.permissions import (
    user_has_role,
    user_states,
    user_territories,
)

logger = logging.getLogger("apps.core.permissions")

SAFE_METHODS = ("GET", "HEAD", "OPTIONS")


def _resolve_territorio_id(obj: Any, path: str) -> int | None:
    """Traversal: 'upf.territorio_id' → obj.upf.territorio_id"""
    current = obj
    for attr in path.split("."):
        current = getattr(current, attr, None)
        if current is None:
            return None
    return current  # type: ignore[return-value]


def _log_denial(user: Any, view: APIView, obj: Any | None = None, *, reason: str = "") -> None:
    obj_id = getattr(obj, "pk", None) if obj else None
    view_name = view.__class__.__name__ if view else "UnknownView"
    logger.warning(
        "Permissão negada: user_id=%s view=%s object_id=%s reason=%s",
        getattr(user, "pk", None),
        view_name,
        obj_id,
        reason,
    )


class IsSuperAdmin(BasePermission):
    """Perfil super-admin — bypass total."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        if user_has_role(request.user, "super-admin"):
            return True
        _log_denial(request.user, view, reason="role != super-admin")
        return False

    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool:
        return self.has_permission(request, view)


class IsUGP(BasePermission):
    """Perfil ugp — acesso global."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        if user_has_role(request.user, "ugp"):
            return True
        _log_denial(request.user, view, reason="role != ugp")
        return False

    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool:
        return self.has_permission(request, view)


class IsArticuladorEstadual(BasePermission):
    """Perfil articulador-estadual. Object-level: território em estado do usuário."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        if user_has_role(request.user, "articulador-estadual"):
            return True
        _log_denial(request.user, view, reason="role != articulador-estadual")
        return False

    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool:
        if not self.has_permission(request, view):
            return False

        from apps.core.models.territory import Territory

        path = getattr(view, "_territorio_attr_path", "territorio_id")
        territorio_id = _resolve_territorio_id(obj, path)

        if territorio_id is None:
            _log_denial(request.user, view, obj, reason="objeto sem territorio_id resolvido")
            return False

        try:
            territorio = Territory.objects.get(pk=territorio_id)
        except Territory.DoesNotExist:
            _log_denial(request.user, view, obj, reason=f"territorio_id={territorio_id} não encontrado")
            return False

        obj_states = set(territorio.estados or [])
        allowed_states = user_states(request.user)

        if obj_states & allowed_states:
            return True

        _log_denial(
            request.user, view, obj,
            reason=f"estados do territorio={obj_states} fora do escopo={allowed_states}",
        )
        return False


class IsADTInTerritory(BasePermission):
    """Perfil adt-acr. Object-level: território vinculado ao usuário."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        if user_has_role(request.user, "adt-acr"):
            return True
        _log_denial(request.user, view, reason="role != adt-acr")
        return False

    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool:
        if not self.has_permission(request, view):
            return False

        path = getattr(view, "_territorio_attr_path", "territorio_id")
        territorio_id = _resolve_territorio_id(obj, path)

        if territorio_id is None:
            _log_denial(request.user, view, obj, reason="objeto sem territorio_id resolvido")
            return False

        allowed_ids = set(user_territories(request.user).values_list("pk", flat=True))

        if territorio_id in allowed_ids:
            return True

        _log_denial(
            request.user, view, obj,
            reason=f"territorio_id={territorio_id} fora dos territorios do usuario",
        )
        return False


class IsFGD(BasePermission):
    """Perfil fgd."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        if user_has_role(request.user, "fgd"):
            return True
        _log_denial(request.user, view, reason="role != fgd")
        return False

    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool:
        return self.has_permission(request, view)


class IsOwnerOrReadOnly(BasePermission):
    """Só o criador (criado_por) edita; demais são read-only."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        return True

    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool:
        if request.method in SAFE_METHODS:
            return True

        criado_por = getattr(obj, "criado_por", None)
        if criado_por is not None and criado_por == request.user:
            return True

        criado_por_id = getattr(obj, "criado_por_id", None)
        if criado_por_id is not None and criado_por_id == request.user.pk:
            return True

        _log_denial(request.user, view, obj, reason="usuario nao e o criador do objeto")
        return False
