"""Geração de arquivos de exportação do SGP, síncrona ou via ExportJob.

Os três datasets (Plano de Trabalho, Atividades e UPFs) passam pela mesma
geração de CSV/XLSX, e o fluxo assíncrono reaproveita a mesma validação de
filtros das rotas síncronas — um filtro aceito numa é aceito na outra.
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from io import BytesIO, StringIO
from typing import Callable

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError

from apps.sgp.exceptions import ErroComCodigo
from apps.sgp.models import ExportJob
from apps.sgp.serializers.exportacao import AtividadesExportQuerySerializer
from apps.sgp.serializers_workplan import WorkPlanExportQuerySerializer
from apps.sgp.services import activity_export, upf_export, workplan_export

logger = logging.getLogger(__name__)

CONTENT_TYPES = {
    ExportJob.Formato.CSV: "text/csv; charset=utf-8",
    ExportJob.Formato.XLSX: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

VALIDADE_ARQUIVO = timedelta(hours=24)
# Exportações que nunca chegaram a gerar arquivo (erro ou worker parado) não
# têm `expira_em`; somem depois deste prazo.
RETENCAO_SEM_ARQUIVO = timedelta(days=7)


@dataclass(frozen=True)
class TipoExportacao:
    prefixo_arquivo: str
    titulo_planilha: str
    colunas: tuple
    linhas: Callable[..., list[dict[str, str]]]
    # None: os filtros são os do UPFFilter, validados por `upf_export`.
    query_serializer: type | None


def _linhas_upfs(*, user, **filtros):
    queryset = upf_export.upf_export_queryset(user=user, filtros=filtros)
    return upf_export.upf_export_rows(queryset, user=user)


TIPOS = {
    ExportJob.Tipo.PLANO_TRABALHO: TipoExportacao(
        "plano_trabalho", "Plano de Trabalho", workplan_export.EXPORT_COLUMNS,
        workplan_export.workplan_export_rows, WorkPlanExportQuerySerializer,
    ),
    ExportJob.Tipo.ATIVIDADES: TipoExportacao(
        "atividades", "Atividades", activity_export.EXPORT_COLUMNS,
        activity_export.activity_export_rows, AtividadesExportQuerySerializer,
    ),
    ExportJob.Tipo.UPFS: TipoExportacao(
        "upfs", "UPFs", upf_export.EXPORT_COLUMNS, _linhas_upfs, None,
    ),
}


@dataclass(frozen=True)
class Arquivo:
    conteudo: bytes
    nome: str
    content_type: str


def gerar_arquivo(columns, rows, formato: str, titulo_planilha: str) -> bytes:
    if formato == ExportJob.Formato.CSV:
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


def _montar_arquivo(tipo: str, formato: str, rows) -> Arquivo:
    definicao = TIPOS[tipo]
    timestamp = timezone.localtime().strftime("%Y-%m-%d_%H-%M-%S")
    return Arquivo(
        conteudo=gerar_arquivo(definicao.colunas, rows, formato, definicao.titulo_planilha),
        nome=f"{definicao.prefixo_arquivo}_{timestamp}.{formato}",
        content_type=CONTENT_TYPES[formato],
    )


def _opcoes(tipo: str, params: dict) -> tuple[str, dict]:
    """Valida `params` (filtros + `formato`) e devolve `(formato, opcoes)`,
    com as opções já no tipo que a função de linhas do `tipo` espera."""
    definicao = TIPOS[tipo]
    if definicao.query_serializer is None:
        return upf_export.separar_parametros(params)

    serializer = definicao.query_serializer(data=params)
    serializer.is_valid(raise_exception=True)
    opcoes = dict(serializer.validated_data)
    return opcoes.pop("formato"), opcoes


def validar_filtros(tipo: str, formato: str, filtros: dict) -> dict:
    """Valida `filtros` para o `tipo` e devolve a versão serializável em JSON
    que fica gravada no ExportJob."""
    try:
        _, opcoes = _opcoes(tipo, {**filtros, "formato": formato})
    except ValidationError as exc:
        raise ValidationError({"filtros": exc.detail})
    if TIPOS[tipo].query_serializer is None:
        return {chave: "" if valor is None else str(valor) for chave, valor in opcoes.items()}
    return {
        chave: valor.isoformat() if isinstance(valor, date) else valor
        for chave, valor in opcoes.items()
    }


def exportar_sincrono(tipo: str, *, user, params: dict) -> Arquivo:
    """Arquivo gerado na própria requisição, a partir dos query params."""
    formato, opcoes = _opcoes(tipo, params)
    return _montar_arquivo(tipo, formato, TIPOS[tipo].linhas(user=user, **opcoes))


def exportar_upfs(*, user, params: dict) -> Arquivo | ExportJob:
    """Até `UPF_EXPORT_SYNC_LIMIT` registros devolve o arquivo; acima disso cria
    um ExportJob para o worker."""
    formato, filtros = _opcoes(ExportJob.Tipo.UPFS, params)
    queryset = upf_export.upf_export_queryset(user=user, filtros=filtros)

    total = queryset.count()
    if total > upf_export.UPF_EXPORT_SYNC_LIMIT:
        return criar_exportacao(
            user=user,
            tipo=ExportJob.Tipo.UPFS,
            formato=formato,
            filtros=validar_filtros(ExportJob.Tipo.UPFS, formato, filtros),
            total_registros=total,
        )
    return _montar_arquivo(
        ExportJob.Tipo.UPFS, formato, upf_export.upf_export_rows(queryset, user=user)
    )


def criar_exportacao(*, user, tipo: str, formato: str, filtros: dict, total_registros=None) -> ExportJob:
    """`filtros` já validados por `validar_filtros`."""
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
            status_code=status.HTTP_409_CONFLICT,
        )
    job.status = ExportJob.Status.PENDENTE
    job.progresso = 0
    job.erro = ""
    job.iniciado_em = None
    job.concluido_em = None
    job.save(update_fields=["status", "progresso", "erro", "iniciado_em", "concluido_em"])
    _enfileirar(job.pk)
    return job


def arquivo_do_job(job: ExportJob) -> Arquivo:
    if job.status != ExportJob.Status.CONCLUIDA:
        raise ErroComCodigo(
            "exportacao_nao_concluida",
            "A exportação ainda não terminou.",
            status_code=status.HTTP_409_CONFLICT,
            status=job.status,
        )
    if job.conteudo is None or (job.expira_em and job.expira_em <= timezone.now()):
        raise ErroComCodigo(
            "exportacao_expirada",
            "O arquivo desta exportação expirou. Gere uma nova exportação.",
            status_code=status.HTTP_410_GONE,
        )
    return Arquivo(bytes(job.conteudo), job.nome_arquivo, job.content_type)


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
        formato, opcoes = _opcoes(job.tipo, {**job.filtros, "formato": job.formato})
        rows = TIPOS[job.tipo].linhas(user=job.solicitante, **opcoes)
        ExportJob.objects.filter(pk=job.pk).update(progresso=60, total_registros=len(rows))
        arquivo = _montar_arquivo(job.tipo, formato, rows)
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
        conteudo=arquivo.conteudo,
        nome_arquivo=arquivo.nome,
        content_type=arquivo.content_type,
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
