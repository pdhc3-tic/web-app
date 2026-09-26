"""Geração de arquivos de exportação do SGP, síncrona ou via ExportJob.

Os três datasets (Plano de Trabalho, Atividades e UPFs) passam pela mesma
geração de CSV/XLSX, e o fluxo assíncrono reaproveita a mesma validação de
filtros das rotas síncronas — um filtro aceito numa é aceito na outra.
"""

from __future__ import annotations

import csv
import logging
from datetime import date, timedelta
from io import BytesIO, StringIO

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError

from apps.sgp.exceptions import ErroComCodigo
from apps.sgp.models import ExportJob
from apps.sgp.services import activity_export, upf_export, workplan_export

logger = logging.getLogger(__name__)

CONTENT_TYPES = {
    "csv": "text/csv; charset=utf-8",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

VALIDADE_ARQUIVO = timedelta(hours=24)
# Exportações que nunca chegaram a gerar arquivo (erro ou worker parado) não
# têm `expira_em`; somem depois deste prazo.
RETENCAO_SEM_ARQUIVO = timedelta(days=7)

TITULOS = {
    ExportJob.Tipo.PLANO_TRABALHO: ("plano_trabalho", "Plano de Trabalho"),
    ExportJob.Tipo.ATIVIDADES: ("atividades", "Atividades"),
    ExportJob.Tipo.UPFS: ("upfs", "UPFs"),
}


def gerar_arquivo(columns, rows, formato: str, titulo_planilha: str) -> bytes:
    if formato == "csv":
        content = StringIO()
        writer = csv.writer(content)
        writer.writerow([label for _, label in columns])
        for row in rows:
            writer.writerow([row[key] for key, _ in columns])
        # BOM para o Excel reconhecer UTF-8 ao abrir o CSV direto.
        return ("﻿" + content.getvalue()).encode("utf-8")

    from openpyxl import Workbook

    workbook = Workbook(write_only=True)
    worksheet = workbook.create_sheet(titulo_planilha[:31])
    worksheet.append([label for _, label in columns])
    for row in rows:
        worksheet.append([row[key] for key, _ in columns])
    content = BytesIO()
    workbook.save(content)
    return content.getvalue()


def nome_arquivo(tipo: str, formato: str) -> str:
    prefixo, _ = TITULOS[tipo]
    timestamp = timezone.localtime().strftime("%Y-%m-%d_%H-%M-%S")
    return f"{prefixo}_{timestamp}.{formato}"


def _query_serializer(tipo):
    from apps.sgp.serializers.exportacao import AtividadesExportQuerySerializer
    from apps.sgp.serializers_workplan import WorkPlanExportQuerySerializer

    if tipo == ExportJob.Tipo.PLANO_TRABALHO:
        return WorkPlanExportQuerySerializer
    return AtividadesExportQuerySerializer


def validar_filtros(tipo: str, formato: str, filtros: dict) -> dict:
    """Valida `filtros` para o `tipo` e devolve a versão serializável em JSON
    que fica gravada no ExportJob."""
    if tipo == ExportJob.Tipo.UPFS:
        _, filtros_upf = upf_export.separar_parametros({**filtros, "formato": formato})
        return {
            chave: "" if valor is None else str(valor)
            for chave, valor in filtros_upf.items()
        }

    serializer = _query_serializer(tipo)(data={**filtros, "formato": formato})
    serializer.is_valid(raise_exception=True)
    validados = dict(serializer.validated_data)
    validados.pop("formato")
    return {
        chave: valor.isoformat() if isinstance(valor, date) else valor
        for chave, valor in validados.items()
    }


def montar_dataset(tipo: str, *, user, formato: str, filtros: dict):
    """Devolve `(columns, rows)` do dataset do `tipo` no escopo do usuário."""
    if tipo == ExportJob.Tipo.UPFS:
        queryset = upf_export.upf_export_queryset(user=user, filtros=filtros)
        return upf_export.EXPORT_COLUMNS, upf_export.upf_export_rows(queryset, user=user)

    serializer = _query_serializer(tipo)(data={**filtros, "formato": formato})
    serializer.is_valid(raise_exception=True)
    opcoes = dict(serializer.validated_data)
    opcoes.pop("formato")

    if tipo == ExportJob.Tipo.PLANO_TRABALHO:
        return workplan_export.EXPORT_COLUMNS, workplan_export.workplan_export_rows(
            user=user, **opcoes
        )
    return activity_export.EXPORT_COLUMNS, activity_export.activity_export_rows(
        user=user, **opcoes
    )


def criar_exportacao(*, user, tipo: str, formato: str, filtros: dict, total_registros=None) -> ExportJob:
    job = ExportJob.objects.create(
        tipo=tipo,
        formato=formato,
        filtros=filtros,
        solicitante=user,
        total_registros=total_registros,
    )
    _enfileirar(job.pk)
    return job


def repetir_exportacao(job: ExportJob) -> ExportJob:
    if job.status != ExportJob.Status.ERRO:
        raise ErroComCodigo(
            "exportacao_nao_repetivel",
            "Só é possível repetir uma exportação que terminou com erro.",
            status_code=409,
        )
    job.status = ExportJob.Status.PENDENTE
    job.progresso = 0
    job.erro = ""
    job.iniciado_em = None
    job.concluido_em = None
    job.save(update_fields=["status", "progresso", "erro", "iniciado_em", "concluido_em"])
    _enfileirar(job.pk)
    return job


def _enfileirar(job_id: int) -> None:
    from apps.sgp.tasks import processar_exportacao

    transaction.on_commit(lambda: processar_exportacao.delay(job_id))


def executar_exportacao(job_id: int) -> None:
    with transaction.atomic():
        job = (
            ExportJob.objects.select_for_update()
            .select_related("solicitante")
            .filter(pk=job_id)
            .first()
        )
        # Reentrega da mensagem pelo broker ou job já apagado: nada a fazer.
        if job is None or job.status != ExportJob.Status.PENDENTE:
            return
        job.status = ExportJob.Status.PROCESSANDO
        job.progresso = 10
        job.iniciado_em = timezone.now()
        job.save(update_fields=["status", "progresso", "iniciado_em"])

    try:
        columns, rows = montar_dataset(
            job.tipo,
            user=job.solicitante,
            formato=job.formato,
            filtros=job.filtros,
        )
        ExportJob.objects.filter(pk=job.pk).update(progresso=60, total_registros=len(rows))
        _, titulo = TITULOS[job.tipo]
        conteudo = gerar_arquivo(columns, rows, job.formato, titulo)
    except (PermissionDenied, ValidationError, ErroComCodigo) as exc:
        _marcar_erro(job.pk, _mensagem_de(exc))
        return
    except Exception:
        logger.exception("Falha ao gerar a exportação %s", job.pk)
        _marcar_erro(job.pk, "Falha inesperada ao gerar a exportação. Tente novamente.")
        return

    agora = timezone.now()
    ExportJob.objects.filter(pk=job.pk).update(
        status=ExportJob.Status.CONCLUIDA,
        progresso=100,
        conteudo=conteudo,
        nome_arquivo=nome_arquivo(job.tipo, job.formato),
        content_type=CONTENT_TYPES[job.formato],
        concluido_em=agora,
        expira_em=agora + VALIDADE_ARQUIVO,
    )


def _marcar_erro(job_id: int, mensagem: str) -> None:
    ExportJob.objects.filter(pk=job_id).update(
        status=ExportJob.Status.ERRO,
        erro=mensagem,
        concluido_em=timezone.now(),
    )


def _mensagem_de(exc: APIException) -> str:
    detail = exc.detail
    if isinstance(detail, dict) and "message" in detail:
        return str(detail["message"])
    if isinstance(detail, dict):
        partes = []
        for campo, erros in detail.items():
            erros = erros if isinstance(erros, list) else [erros]
            partes.append(f"{campo}: {' '.join(str(e) for e in erros)}")
        return "Filtros inválidos — " + "; ".join(partes)
    if isinstance(detail, list):
        return " ".join(str(e) for e in detail)
    return str(detail)


def limpar_exportacoes_expiradas() -> int:
    agora = timezone.now()
    expiradas = ExportJob.objects.filter(expira_em__lt=agora)
    abandonadas = ExportJob.objects.filter(
        expira_em__isnull=True, criado_em__lt=agora - RETENCAO_SEM_ARQUIVO
    )
    removidas, _ = (expiradas | abandonadas).delete()
    return removidas
