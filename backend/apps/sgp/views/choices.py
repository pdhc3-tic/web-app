from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAuthenticatedActiveAccess
from apps.sgp.constants import (
    AGUA_CHOICES,
    COR_RACA_CHOICES,
    DISPOSITIVO_CHOICES,
    ENERGIA_CHOICES,
    ESCOLARIDADE_CHOICES,
    GENERO_CHOICES,
    MATERIAL_CONSTRUCAO_CHOICES,
    PARENTESCO_CHOICES,
    PCT_CHOICES,
    POSSE_TERRA_CHOICES,
    SAUDE_CHOICES,
    SITUACAO_MORADIA_CHOICES,
    TIPO_MORADIA_CHOICES,
)


class SGPChoicesView(APIView):
    permission_classes = [IsAuthenticatedActiveAccess]
    http_method_names = ["get", "head", "options"]

    def get(self, request):
        choices = {
            "genero": [{"value": v, "label": l} for v, l in GENERO_CHOICES],
            "cor_raca": [{"value": v, "label": l} for v, l in COR_RACA_CHOICES],
            "escolaridade": [{"value": v, "label": l} for v, l in ESCOLARIDADE_CHOICES],
            "dispositivo": [{"value": v, "label": l} for v, l in DISPOSITIVO_CHOICES],
            "pct": [{"value": v, "label": l} for v, l in PCT_CHOICES],
            "posse_terra": [{"value": v, "label": l} for v, l in POSSE_TERRA_CHOICES],
            "situacao_moradia": [{"value": v, "label": l} for v, l in SITUACAO_MORADIA_CHOICES],
            "tipo_moradia": [{"value": v, "label": l} for v, l in TIPO_MORADIA_CHOICES],
            "material_construcao": [{"value": v, "label": l} for v, l in MATERIAL_CONSTRUCAO_CHOICES],
            "energia": [{"value": v, "label": l} for v, l in ENERGIA_CHOICES],
            "agua": [{"value": v, "label": l} for v, l in AGUA_CHOICES],
            "grau_parentesco": [{"value": v, "label": l} for v, l in PARENTESCO_CHOICES],
            "saude": [{"value": v, "label": v} for v in SAUDE_CHOICES],
        }
        return Response(choices)
