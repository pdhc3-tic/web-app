import csv
import json
from io import BytesIO, StringIO
from xml.sax.saxutils import escape

from django.shortcuts import get_object_or_404
from django.http import FileResponse, HttpResponse
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAuthenticatedActiveAccess
from apps.core.services.permissions import user_has_role, user_states, user_territories
from apps.sgp.filters import FormResponseFilter
from apps.sgp.models import FormResponse, UPF
from apps.sgp.pagination import HistoricoPagination
from apps.sgp.serializers import (
    AvailableFormSerializer,
    FormResponseDetailSerializer,
    FormResponseListSerializer,
    FormResponseReceiveSerializer,
)
from apps.sgp.services.forms import get_available_upf_forms


def accessible_upf_queryset(user):
    queryset = UPF.objects.select_related("municipio", "municipio__state", "territorio")

    if user_has_role(user, "super-admin") or user_has_role(user, "ugp"):
        return queryset

    if user_has_role(user, "articulador-estadual"):
        states = user_states(user)
        return queryset.filter(municipio__state__sigla__in=states) if states else queryset.none()

    if user_has_role(user, "adt-acr"):
        territories = user_territories(user)
        return queryset.filter(territorio__in=territories) if territories.exists() else queryset.none()

    raise PermissionDenied("Você não tem acesso ao módulo SGP.")


class FormResponseExportQuerySerializer(serializers.Serializer):
    formato = serializers.ChoiceField(choices=["csv", "pdf"])


class FormResponseViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticatedActiveAccess]
    pagination_class = HistoricoPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = FormResponseFilter
    http_method_names = ["get", "head", "options"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return FormResponseDetailSerializer
        return FormResponseListSerializer

    def _accessible_upf_queryset(self):
        return accessible_upf_queryset(self.request.user)

    def get_upf(self):
        if not hasattr(self, "_upf"):
            self._upf = get_object_or_404(
                self._accessible_upf_queryset(),
                pk=self.kwargs["upf_pk"],
            )
        return self._upf

    def get_queryset(self):
        return FormResponse.objects.filter(upf=self.get_upf()).order_by(
            "-data_preenchimento", "-pk"
        )

    @extend_schema(
        parameters=[
            OpenApiParameter("formulario_id", OpenApiTypes.INT, OpenApiParameter.QUERY),
            OpenApiParameter("data_inicio", OpenApiTypes.DATE, OpenApiParameter.QUERY),
            OpenApiParameter("data_fim", OpenApiTypes.DATE, OpenApiParameter.QUERY),
            OpenApiParameter("respondente", OpenApiTypes.STR, OpenApiParameter.QUERY),
        ],
        responses=FormResponseListSerializer(many=True),
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(responses=FormResponseDetailSerializer)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "formato",
                OpenApiTypes.STR,
                OpenApiParameter.QUERY,
                required=True,
                enum=["csv", "pdf"],
            ),
            OpenApiParameter("formulario_id", OpenApiTypes.INT, OpenApiParameter.QUERY),
            OpenApiParameter("data_inicio", OpenApiTypes.DATE, OpenApiParameter.QUERY),
            OpenApiParameter("data_fim", OpenApiTypes.DATE, OpenApiParameter.QUERY),
            OpenApiParameter("respondente", OpenApiTypes.STR, OpenApiParameter.QUERY),
        ],
        responses={200: OpenApiTypes.BINARY},
    )
    def export(self, request, *args, **kwargs):
        query_serializer = FormResponseExportQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)

        responses = self.filter_queryset(self.get_queryset())
        formato = query_serializer.validated_data["formato"]
        timestamp = timezone.localtime().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"respostas_formularios_upf_{self.get_upf().pk}_{timestamp}.{formato}"

        if formato == "csv":
            return self._csv_response(responses, filename)
        return self._pdf_response(responses, filename)

    @staticmethod
    def _csv_response(responses, filename):
        content = StringIO()
        writer = csv.writer(content)
        writer.writerow(
            [
                "ID",
                "Formulário",
                "Versão",
                "Data de preenchimento",
                "Respondente",
                "Status",
                "Origem",
                "Respostas",
            ]
        )
        for response in responses:
            writer.writerow(
                [
                    response.pk,
                    response.formulario_nome,
                    response.formulario_versao,
                    timezone.localtime(response.data_preenchimento).isoformat(),
                    response.respondente or "Anônimo",
                    response.get_status_display(),
                    response.get_origem_display(),
                    json.dumps(response.respostas_json, ensure_ascii=False, default=str),
                ]
            )

        return HttpResponse(
            "\ufeff" + content.getvalue(),
            content_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @staticmethod
    def _pdf_response(responses, filename):
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

        content = BytesIO()
        document = SimpleDocTemplate(
            content,
            pagesize=A4,
            leftMargin=2 * cm,
            rightMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
            title="Respostas de formulários da UPF",
        )
        styles = getSampleStyleSheet()
        metadata_style = ParagraphStyle(
            "FormResponseMetadata",
            parent=styles["BodyText"],
            leading=15,
        )
        json_style = ParagraphStyle(
            "FormResponseJson",
            parent=styles["Code"],
            fontName="Courier",
            fontSize=7,
            leading=9,
        )
        story = [Paragraph("Respostas de formulários", styles["Title"])]

        for index, response in enumerate(responses):
            if index:
                story.append(PageBreak())

            story.extend(
                [
                    Paragraph(
                        escape(f"{response.formulario_nome} (v{response.formulario_versao})"),
                        styles["Heading1"],
                    ),
                    Paragraph(
                        "<br/>".join(
                            [
                                f"<b>Data de preenchimento:</b> {timezone.localtime(response.data_preenchimento).strftime('%d/%m/%Y %H:%M')}",
                                f"<b>Respondente:</b> {escape(response.respondente or 'Anônimo')}",
                                f"<b>Status:</b> {escape(response.get_status_display())}",
                                f"<b>Origem:</b> {escape(response.get_origem_display())}",
                            ]
                        ),
                        metadata_style,
                    ),
                    Spacer(1, 0.4 * cm),
                    Paragraph("Respostas", styles["Heading2"]),
                    Paragraph(
                        escape(
                            json.dumps(
                                response.respostas_json,
                                ensure_ascii=False,
                                indent=2,
                                default=str,
                            )
                        ).replace("\n", "<br/>"),
                        json_style,
                    ),
                ]
            )

        document.build(story)
        content.seek(0)
        return FileResponse(
            content,
            as_attachment=True,
            filename=filename,
            content_type="application/pdf",
        )


class AvailableFormListView(APIView):
    permission_classes = [IsAuthenticatedActiveAccess]

    @extend_schema(responses=AvailableFormSerializer(many=True))
    def get(self, request):
        forms = get_available_upf_forms(request.user)
        return Response(AvailableFormSerializer(forms, many=True).data)


class FormResponseReceiveView(APIView):
    permission_classes = [IsAuthenticatedActiveAccess]

    @extend_schema(
        request=FormResponseReceiveSerializer,
        responses={
            200: FormResponseDetailSerializer,
            201: FormResponseDetailSerializer,
        },
        description=(
            "Recebe uma resposta concluída do contrato `1.0`. "
            "Reenvios com a mesma combinação de `origem` e "
            "`resposta_id_origem` retornam o registro existente."
        ),
        examples=[
            OpenApiExample(
                "Resposta submetida pelo SCA",
                value={
                    "upf_id": 1,
                    "formulario_id": 10,
                    "formulario_nome": "Diagnóstico produtivo",
                    "formulario_versao": "1.0",
                    "respondente": "Técnico de campo",
                    "status": "submetido",
                    "respostas_json": {"atividade_principal": "Agricultura"},
                    "origem": "sca",
                    "contract_version": "1.0",
                    "resposta_id_origem": "sca-9c4f9c8d",
                },
                request_only=True,
            ),
        ],
    )
    def post(self, request):
        serializer = FormResponseReceiveSerializer(
            data=request.data,
            context={"upf_queryset": accessible_upf_queryset(request.user)},
        )
        serializer.is_valid(raise_exception=True)
        form_response = serializer.save()
        response_status = (
            status.HTTP_201_CREATED if form_response._was_created else status.HTTP_200_OK
        )
        return Response(
            FormResponseDetailSerializer(form_response).data,
            status=response_status,
        )
