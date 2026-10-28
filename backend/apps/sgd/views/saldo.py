from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAuthenticatedActiveAccess
from apps.sgd.serializers.saldo import SaldoConsultaQuerySerializer, SaldoConsultaSerializer
from apps.sgd.services import balance as balance_service
from apps.sgd.services.demand_request import rubrica_para_tipo
from apps.sgp.models import Activity, BudgetRubrica


class SaldoConsultaView(APIView):
    permission_classes = [IsAuthenticatedActiveAccess]

    def get(self, request):
        query = SaldoConsultaQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        dados = query.validated_data

        activity = get_object_or_404(Activity.objects.select_related("acao"), pk=dados["activity_id"])
        slug = dados["rubrica"] if "rubrica" in dados else rubrica_para_tipo(dados["tipo"]).slug
        rubrica = BudgetRubrica.objects.filter(slug=slug, ativo=True).first()
        if rubrica is None:
            raise DRFValidationError({"rubrica": f"Rubrica '{slug}' não existe ou está inativa."})

        check = balance_service.verificar_duas_travas(
            solicitante=request.user, rubrica=rubrica, valor=dados["valor"], activity=activity,
        )
        payload = balance_service.payload_saldo_consulta(
            check, solicitante=request.user, rubrica=rubrica, valor=dados["valor"],
        )
        payload.update(rubrica_slug=rubrica.slug, rubrica_nome=rubrica.nome)
        return Response(SaldoConsultaSerializer(payload).data)
