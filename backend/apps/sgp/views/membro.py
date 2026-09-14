import csv
from datetime import date
from io import StringIO

from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models.audit_log import AuditLog
from apps.core.permissions import IsAuthenticatedActiveAccess
from apps.core.services.membro_audit import log_membro_change, sensitive_fields_changed
from apps.sgp.models import MembroFamilia, UPF
from apps.sgp.serializers import (
    MembroDetailSerializer,
    MembroExportQuerySerializer,
    MembroListSerializer,
)
from apps.sgp.services.membro_export import (
    MEMBROS_EXPORT_UPF_LIMIT,
    ExportLimitExceeded,
    membro_export_rows_for_scope,
    membro_export_rows_for_upf,
)
from apps.sgp.views.upf import upfs_acessiveis_ao_usuario


def data_limite_aniversario(hoje, anos):
    """Data mínima para quem ainda não completou `anos` anos hoje.

    Corresponde ao aniversário de `anos` anos atrás: quem nasceu nesta data
    ou depois ainda não completou `anos` anos. Em anos não bissextos, um
    aniversário que cairia em 29/fev é tratado como 28/fev.
    """
    try:
        return date(hoje.year - anos, hoje.month, hoje.day)
    except ValueError:
        return date(hoje.year - anos, hoje.month, 28)


def _membros_csv_response(columns, rows, filename):
    """CSV UTF-8 com BOM, no mesmo formato de `WorkPlanExportView` (docs/export.md)."""
    content = StringIO()
    writer = csv.writer(content)
    writer.writerow([label for _, label in columns])
    for row in rows:
        writer.writerow([row.get(key, "") for key, _ in columns])
    response = HttpResponse(
        "\ufeff" + content.getvalue(),
        content_type="text/csv; charset=utf-8",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


class MembroViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticatedActiveAccess]
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_upf(self):
        upf_pk = self.kwargs["upf_pk"]
        return get_object_or_404(upfs_acessiveis_ao_usuario(self.request.user), pk=upf_pk)

    def get_queryset(self):
        upf = self.get_upf()
        return MembroFamilia.objects.filter(upf=upf)

    def get_serializer_class(self):
        if self.action == "list":
            return MembroListSerializer
        return MembroDetailSerializer

    def perform_create(self, serializer):
        upf = self.get_upf()
        if not upf.ativa:
            raise serializers.ValidationError(
                "Não é possível adicionar membros a uma UPF inativa"
            )
        try:
            instance = serializer.save(upf=upf, criado_por=self.request.user, ultima_origem="web")
        except IntegrityError as e:
            if "unique_cpf_global" in str(e):
                raise serializers.ValidationError(
                    {"cpf": "Já existe um membro cadastrado com este CPF"}
                )
            raise
        log_membro_change(
            user=self.request.user,
            acao="MEMBRO.create",
            membro=instance,
            origem="web",
            campos_alterados=sensitive_fields_changed(
                None, {"saude": instance.saude, "cor_raca": instance.cor_raca}
            ),
            request=self.request,
        )

    def perform_update(self, serializer):
        old = self.get_object()
        if old.pk == old.upf.titular_id and "grau_parentesco" in serializer.validated_data:
            if serializer.validated_data["grau_parentesco"] != "titular":
                raise serializers.ValidationError(
                    {"grau_parentesco": "Não é possível alterar o parentesco do titular. Use o endpoint de transferência de titularidade."}
                )
        valores_anteriores = {
            "membro_id": old.pk,
            "upf_id": old.upf_id,
            "nome_completo": old.nome_completo,
            "grau_parentesco": old.grau_parentesco,
            "cpf": old.cpf,
        }
        anteriores_sensiveis = {"saude": old.saude, "cor_raca": old.cor_raca}
        try:
            instance = serializer.save(ultima_origem="web")
        except IntegrityError as e:
            if "unique_cpf_global" in str(e):
                raise serializers.ValidationError(
                    {"cpf": "Já existe um membro cadastrado com este CPF"}
                )
            raise

        # Nunca grava o valor de saúde/cor-raça, só o nome de quem mudou.
        log_membro_change(
            user=self.request.user,
            acao="MEMBRO.update",
            membro=instance,
            origem="web",
            campos_alterados=sensitive_fields_changed(
                anteriores_sensiveis, {"saude": instance.saude, "cor_raca": instance.cor_raca}
            ),
            request=self.request,
            valores_anteriores=valores_anteriores,
        )

    def perform_destroy(self, instance):
        upf = instance.upf
        if upf.titular_id == instance.pk:
            outros = MembroFamilia.objects.filter(upf=upf).exclude(pk=instance.pk)
            if not outros.exists():
                raise serializers.ValidationError(
                    "Não é possível excluir o único titular da UPF"
                )
            raise serializers.ValidationError(
                "Transfira a titularidade para outro membro antes de excluir"
            )
        log_membro_change(
            user=self.request.user,
            acao="MEMBRO.delete",
            membro=instance,
            origem="web",
            campos_alterados=sensitive_fields_changed(
                None, {"saude": instance.saude, "cor_raca": instance.cor_raca}
            ),
            request=self.request,
            valores_anteriores={
                "membro_id": instance.pk,
                "upf_id": instance.upf_id,
                "nome_completo": instance.nome_completo,
                "grau_parentesco": instance.grau_parentesco,
            },
        )
        instance.delete()

    @action(detail=False, methods=["get"], url_path="exportar")
    def exportar(self, request, upf_pk=None):
        """Exporta em CSV os membros de uma UPF específica (Issue #186)."""
        upf = self.get_upf()
        columns, rows = membro_export_rows_for_upf(upf, user=request.user)
        timestamp = timezone.localtime().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"membros_upf_{upf.pk}_{timestamp}.csv"
        return _membros_csv_response(columns, rows, filename)

    @action(detail=False, methods=["get"], url_path="resumo")
    def resumo(self, request, upf_pk=None):
        from django.db.models import Count, Case, When, IntegerField, Value, Q
        from django.db.models.functions import Coalesce

        upf = self.get_upf()
        hoje = date.today()

        membros = MembroFamilia.objects.filter(upf=upf)

        total = membros.count()
        tem_titular = membros.filter(grau_parentesco="titular").exists()

        faixa_agg = membros.aggregate(
            faixa_0_11=Count(
                "pk",
                filter=Q(data_nascimento__isnull=False) & Q(data_nascimento__gt=data_limite_aniversario(hoje, 12))
            ),
            faixa_12_17=Count(
                "pk",
                filter=Q(data_nascimento__isnull=False)
                & Q(data_nascimento__lte=data_limite_aniversario(hoje, 12))
                & Q(data_nascimento__gt=data_limite_aniversario(hoje, 18))
            ),
            faixa_18_59=Count(
                "pk",
                filter=Q(data_nascimento__isnull=False)
                & Q(data_nascimento__lte=data_limite_aniversario(hoje, 18))
                & Q(data_nascimento__gt=data_limite_aniversario(hoje, 60))
            ),
            faixa_60_mais=Count(
                "pk",
                filter=Q(data_nascimento__isnull=False) & Q(data_nascimento__lte=data_limite_aniversario(hoje, 60))
            ),
            sem_data_nasc=Count("pk", filter=Q(data_nascimento__isnull=True)),
        )

        faixa_etaria = {
            "0-11": faixa_agg["faixa_0_11"],
            "12-17": faixa_agg["faixa_12_17"],
            "18-59": faixa_agg["faixa_18_59"],
            "60+": faixa_agg["faixa_60_mais"],
            "sem_data_nascimento": faixa_agg["sem_data_nasc"],
        }

        genero_agg = membros.aggregate(
            masculino=Count("pk", filter=Q(genero=1)),
            feminino=Count("pk", filter=Q(genero=2)),
            nao_binario=Count("pk", filter=Q(genero=3)),
            nao_informado=Count("pk", filter=Q(genero=4) | Q(genero__isnull=True)),
        )

        genero = {
            "masculino": genero_agg["masculino"],
            "feminino": genero_agg["feminino"],
            "nao_binario": genero_agg["nao_binario"],
            "nao_informado": genero_agg["nao_informado"],
        }

        return Response({
            "total_membros": total,
            "faixa_etaria": faixa_etaria,
            "genero": genero,
            "tem_titular": tem_titular,
        })

    @action(detail=False, methods=["post"], url_path="transferir-titularidade")
    def transferir_titularidade(self, request, upf_pk=None):
        novo_titular_id = request.data.get("novo_titular_id")
        if not novo_titular_id:
            raise serializers.ValidationError(
                {"novo_titular_id": "Campo obrigatório."}
            )

        with transaction.atomic():
            upf = UPF.objects.select_for_update().get(pk=self.kwargs["upf_pk"])
            upfs_visiveis = upfs_acessiveis_ao_usuario(request.user)
            if not upfs_visiveis.filter(pk=upf.pk).exists():
                from django.shortcuts import get_object_or_404
                get_object_or_404(UPF, pk=self.kwargs["upf_pk"])

            try:
                novo_titular = MembroFamilia.objects.select_for_update().get(
                    pk=novo_titular_id, upf=upf
                )
            except MembroFamilia.DoesNotExist:
                raise serializers.ValidationError(
                    {"novo_titular_id": "Membro não encontrado nesta UPF."}
                )

            if novo_titular.pk == upf.titular_id:
                raise serializers.ValidationError(
                    {"novo_titular_id": "Este membro já é o titular."}
                )

            antigo_titular = upf.titular
            if antigo_titular:
                antigo_titular = MembroFamilia.objects.select_for_update().get(pk=antigo_titular.pk)

            antigo_titular_grau_parentesco_anterior = antigo_titular.grau_parentesco if antigo_titular else None

            if antigo_titular:
                antigo_titular.grau_parentesco = "filho"
                antigo_titular.save(update_fields=["grau_parentesco"])
            novo_titular.grau_parentesco = "titular"
            novo_titular.save(update_fields=["grau_parentesco"])
            upf.titular = novo_titular
            upf.save(update_fields=["titular"])

        AuditLog.objects.create(
            user=request.user,
            acao="MEMBRO.transferir_titularidade",
            modulo="sgp",
            entidade="UPF",
            entidade_id=str(upf.pk),
            valores_anteriores={
                "upf_id": upf.pk,
                "antigo_titular_id": antigo_titular.pk if antigo_titular else None,
                "antigo_titular_nome": antigo_titular.nome_completo if antigo_titular else None,
                "antigo_titular_grau_parentesco": antigo_titular_grau_parentesco_anterior,
            },
            valores_novos={
                "upf_id": upf.pk,
                "novo_titular_id": novo_titular.pk,
                "novo_titular_nome": novo_titular.nome_completo,
                "novo_titular_grau_parentesco": "titular",
            },
            ip=request.META.get("REMOTE_ADDR"),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )

        return Response({
            "detail": "Titularidade transferida com sucesso.",
            "novo_titular": {
                "id": novo_titular.pk,
                "nome_completo": novo_titular.nome_completo,
            },
            "antigo_titular": {
                "id": antigo_titular.pk,
                "nome_completo": antigo_titular.nome_completo,
            } if antigo_titular else None,
        })


class MembroExportView(APIView):
    """
    Exporta em CSV os membros de múltiplas UPFs dentro do escopo territorial
    do usuário — relatório demográfico agregado (Issue #186).
    """

    permission_classes = [IsAuthenticatedActiveAccess]

    @extend_schema(
        parameters=[
            OpenApiParameter("territorio_id", OpenApiTypes.INT, OpenApiParameter.QUERY),
            OpenApiParameter("municipio", OpenApiTypes.INT, OpenApiParameter.QUERY),
            OpenApiParameter("projeto", OpenApiTypes.INT, OpenApiParameter.QUERY),
        ],
        description=(
            "Exportação territorial agregada de membros, restrita às UPFs "
            "acessíveis ao usuário autenticado. Limitada a "
            f"{MEMBROS_EXPORT_UPF_LIMIT} UPFs por exportação — acima disso, "
            "restrinja por territorio_id, municipio ou projeto."
        ),
    )
    def get(self, request):
        query_serializer = MembroExportQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        filtros = query_serializer.validated_data

        try:
            columns, rows = membro_export_rows_for_scope(user=request.user, **filtros)
        except ExportLimitExceeded as exc:
            return Response(
                {
                    "detail": (
                        f"A exportação abrange {exc.upf_count} UPFs, acima do limite "
                        f"de {exc.limit}. Restrinja por territorio_id, município ou "
                        "projeto."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        timestamp = timezone.localtime().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"membros_{timestamp}.csv"
        return _membros_csv_response(columns, rows, filename)
