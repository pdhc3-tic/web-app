from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAuthenticatedActiveAccess
from apps.sgd.serializers.saldo import SaldoConsultaQuerySerializer, SaldoConsultaSerializer
from apps.sgd.services import balance as balance_service
from apps.sgp.models import Activity
from apps.sgp.models.budget import BudgetRubrica


class SaldoConsultaView(APIView):
    permission_classes = [IsAuthenticatedActiveAccess]

    def get(self, request):
        query = SaldoConsultaQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        dados = query.validated_data

        activity = get_object_or_404(Activity, pk=dados["activity_id"])
        rubrica = BudgetRubrica.objects.filter(slug=dados["rubrica"], ativo=True).first()
        if rubrica is None:
            raise DRFValidationError({"rubrica": f"Rubrica '{dados['rubrica']}' não existe ou está inativa."})

        check = balance_service.verificar_duas_travas(
            solicitante=request.user, rubrica=rubrica, meta=activity.acao.meta, valor=dados["valor"],
        )
        payload = {
            "individual": {
                "disponivel": check.individual.disponivel,
                "saldo": check.individual.saldo,
                "motivo_bloqueio": check.individual.motivo_bloqueio,
            },
            "territorial": {
                "disponivel": check.territorial.disponivel,
                "saldo": check.territorial.saldo,
                "motivo_bloqueio": check.territorial.motivo_bloqueio,
            },
            "disponivel": check.disponivel,
            "trava_bloqueada": check.trava_bloqueada,
        }
        return Response(SaldoConsultaSerializer(payload).data)
