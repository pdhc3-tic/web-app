from rest_framework import status

from apps.core.models import User
from apps.sgp.exceptions import ErroComCodigo


def usuarios_elegiveis_a_tecnico(q: str = ""):
    """Usuários ativos que ainda não são técnicos — opções do cadastro.

    `Tecnico.user` é OneToOne, então quem já tem vínculo (mesmo inativo) não
    pode ganhar outro."""
    queryset = User.objects.filter(
        ativo=True, acesso_revogado=False, tecnico__isnull=True
    ).order_by("nome", "pk")
    q = q.strip()
    if q:
        queryset = queryset.filter(nome__icontains=q)
    return queryset


def desativar_tecnico(tecnico) -> None:
    """Soft-delete via ativo=False. Não afeta Activity.tecnico_responsavel (FK direta a User)."""
    if not tecnico.ativo:
        raise ErroComCodigo(
            "tecnico_ja_inativo",
            "Este técnico já está inativo.",
            status_code=status.HTTP_409_CONFLICT,
        )
    tecnico.ativo = False
    tecnico.save(update_fields=["ativo"])
