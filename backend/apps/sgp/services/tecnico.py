from apps.core.models import User


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
