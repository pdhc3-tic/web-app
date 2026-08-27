from django.db.models import Q

from apps.core.services.permissions import user_territories


def get_available_upf_forms(user) -> list[dict]:
    """Return published UPF forms without making SGP depend on SGF availability."""
    try:
        from apps.sgf.models import FormularioSGF

        territories = user_territories(user)
        if not territories.exists():
            return []

        forms = FormularioSGF.objects.filter(
            status="publicado",
            tipo_entidade_alvo="upf",
        ).filter(
            Q(territorio__in=territories) | Q(territorio__isnull=True)
        ).order_by("atualizado_em")

        return [
            {
                "id": form.pk,
                "nome": form.nome,
                "versao": form.versao,
                "descricao": getattr(form, "descricao", None),
                "atualizado_em": form.atualizado_em,
            }
            for form in forms
        ]
    except Exception:
        return []
