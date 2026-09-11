from datetime import datetime

from django.apps import apps
from django.db.models import Q
from rest_framework.decorators import action

from apps.core.models.audit_log import AuditLog
from apps.sgp.pagination import HistoricoPagination
from apps.sgp.serializers import HistoricoEntrySerializer

# Extraído de UPFViewSet (issue #262) para manter `views/upf.py` sob 400
# linhas — mesmo padrão de mixin já usado por UPFPhotoMixin/UPFDocumentMixin.


class UPFHistoricoMixin:
    @action(detail=True, methods=["get"], url_path="historico")
    def historico(self, request, pk=None):
        upf = self.get_object()
        q = Q(entidade="UPF", entidade_id=str(upf.pk))

        incluir_membros = request.query_params.get("incluir_membros") == "true"
        if incluir_membros:
            MembroFamilia = apps.get_model("sgp", "MembroFamilia")
            if MembroFamilia is not None:
                member_ids = list(
                    MembroFamilia.objects.filter(upf_id=upf.pk).values_list(
                        "pk", flat=True
                    )
                )
                if member_ids:
                    q |= Q(
                        entidade="MembroFamilia",
                        entidade_id__in=[str(m) for m in member_ids],
                    )

        usuario_filter = request.query_params.get("usuario")
        if usuario_filter:
            q &= Q(user_id=usuario_filter)

        desde = request.query_params.get("desde")
        if desde:
            try:
                dt = datetime.fromisoformat(desde)
                q &= Q(timestamp__gte=dt)
            except (ValueError, TypeError):
                pass

        ate = request.query_params.get("ate")
        if ate:
            try:
                dt = datetime.fromisoformat(ate)
                q &= Q(timestamp__lte=dt)
            except (ValueError, TypeError):
                pass

        logs = (
            AuditLog.objects.filter(q)
            .select_related("user")
            .order_by("-timestamp")
        )

        entries = []
        for log in logs:
            if log.acao.lower().endswith(".create"):
                entries.append(
                    self._build_entry(log, campo=None, valor_anterior=None, valor_novo=log.valores_novos)
                )
            elif log.acao.lower().endswith(".update"):
                old = log.valores_anteriores or {}
                new = log.valores_novos or {}
                all_keys = set(old.keys()) | set(new.keys())
                for key in sorted(all_keys):
                    old_val = old.get(key)
                    new_val = new.get(key)
                    if old_val != new_val:
                        entries.append(
                            self._build_entry(log, campo=key, valor_anterior=old_val, valor_novo=new_val, suffix=key)
                        )
            else:
                entries.append(
                    self._build_entry(log, campo=None, valor_anterior=log.valores_anteriores, valor_novo=log.valores_novos)
                )

        campo_filter = request.query_params.get("campo")
        if campo_filter:
            entries = [e for e in entries if e["campo"] == campo_filter]

        paginator = HistoricoPagination()
        page = paginator.paginate_queryset(entries, request)
        serializer = HistoricoEntrySerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def _build_entry(self, log, campo, valor_anterior, valor_novo, suffix=None):
        eid = str(log.pk) if suffix is None else f"{log.pk}_{suffix}"
        return {
            "id": eid,
            "campo": campo,
            "valor_anterior": valor_anterior,
            "valor_novo": valor_novo,
            "usuario_id": log.user.pk if log.user else None,
            "usuario_nome": log.user.nome if log.user else None,
            "timestamp": log.timestamp,
        }
