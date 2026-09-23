from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAuthenticatedActiveAccess
from apps.sgd.serializers.saldo import SaldoConsultaQuerySerializer, SaldoConsultaSerializer
from apps.sgd.services import balance as balance_service
from apps.sgp.models import Activity
from apps.sgp.models.budget import BudgetRubrica
from apps.sgp.services import budget as budget_service


def _semaforo_territorial(allocation) -> str | None:
    # Painel do SGP usa limiares próprios (60/80), diferentes do 70/90 do
    # SGD — quem é dono do saldo territorial é o SGP.
    if allocation is None:
        return None
    percentual = balance_service.percentual_comprometido(allocation.valor_comprometido, allocation.valor_alocado)
    if percentual >= budget_service.LIMIAR_SEMAFORO_VERMELHO:
        return "vermelho"
    if percentual >= budget_service.LIMIAR_SEMAFORO_AMARELO:
        return "amarelo"
    return "verde"


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
        limite = balance_service.DemandIndividualLimit.objects.filter(
            solicitante=request.user, rubrica=rubrica,
        ).first()
        semaforo_individual = None
        if limite is not None:
            semaforo_individual = balance_service.semaforo_sgd(
                balance_service.percentual_comprometido(limite.valor_comprometido, limite.valor_limite)
            )
        payload = {
            "individual": {
                "disponivel": check.individual.disponivel,
                "saldo": check.individual.saldo,
                "motivo_bloqueio": check.individual.motivo_bloqueio,
                "acao_sugerida": check.individual.acao_sugerida,
                "semaforo": semaforo_individual,
            },
            "territorial": {
                "disponivel": check.territorial.disponivel,
                "saldo": check.territorial.saldo,
                "motivo_bloqueio": check.territorial.motivo_bloqueio,
                "acao_sugerida": (
                    None if check.territorial.disponivel
                    else balance_service.ACAO_SUGERIDA[balance_service.TRAVA_TERRITORIAL]
                ),
                "semaforo": _semaforo_territorial(check.territorial.allocation),
            },
            "disponivel": check.disponivel,
            "trava_bloqueada": check.trava_bloqueada,
        }
        return Response(SaldoConsultaSerializer(payload).data)
