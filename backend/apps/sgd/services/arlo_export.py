"""Exportação das demandas autorizadas para o Arlo (SGD-RF31)."""
from uuid import uuid4

from django.db import transaction

from apps.core.storage import get_storage
from apps.sgd.models.arlo_import import ArloImport
from apps.sgd.models.demand import Demand
from apps.sgd.services.arlo_mapping import obter_mapeamento
from apps.sgp.models import ExportJob
from apps.sgp.services.exportacao import gerar_arquivo

CONTENT_TYPE_CSV = "text/csv"


def _rotulo(numero, titulo) -> str:
    return f"{numero} - {titulo}" if titulo else str(numero)


def _linha(demand, solicitacao) -> dict:
    acao = demand.activity.acao
    return {
        "demanda_id": demand.pk,
        "solicitacao_id": solicitacao.pk,
        "titulo": demand.titulo,
        "meta": _rotulo(acao.meta.numero, acao.meta.titulo),
        "submeta": _rotulo(acao.submeta.numero, acao.submeta.titulo),
        "acao": _rotulo(acao.numero, acao.descricao),
        "indicador": _rotulo(acao.indicador.codigo, acao.indicador.nome),
        "atividade": demand.activity.titulo,
        "rubrica": solicitacao.rubrica.nome,
        "solicitante": demand.solicitante.nome,
        "valor_estimado": solicitacao.valor_estimado,
        "valor_autorizado": solicitacao.valor_autorizado if solicitacao.valor_autorizado is not None
        else solicitacao.valor_estimado,
    }


def demandas_autorizadas():
    return (
        Demand.objects.filter(status="autorizada")
        .select_related(
            "solicitante", "activity__acao__meta", "activity__acao__submeta", "activity__acao__indicador",
        )
        .prefetch_related("solicitacoes__rubrica")
        .order_by("pk")
    )


def gerar_csv(demandas=None) -> tuple[bytes, int]:
    """Uma linha por solicitação (rubrica) — é a granularidade do pagamento."""
    mapeamento = obter_mapeamento()["exportacao"]
    columns = [(item["campo"], item["coluna"]) for item in mapeamento]
    rows = [
        _linha(demand, solicitacao)
        for demand in (demandas_autorizadas() if demandas is None else demandas)
        for solicitacao in sorted(demand.solicitacoes.all(), key=lambda s: (s.rubrica_id, s.pk))
    ]
    return gerar_arquivo(columns, rows, ExportJob.Formato.CSV, "Arlo"), len(rows)


@transaction.atomic
def exportar(*, usuario) -> tuple[ArloImport, bytes]:
    conteudo, total = gerar_csv()
    key = f"arlo/exportacoes/{uuid4()}.csv"
    storage = get_storage()
    storage.save_from_bytes(key, conteudo, content_type=CONTENT_TYPE_CSV)
    importacao = ArloImport.objects.create(
        tipo=ArloImport.Tipo.EXPORTACAO,
        status=ArloImport.Status.CONCLUIDO,
        arquivo_key=key,
        arquivo_url=storage.get_public_url(key),
        nome_original=key.rsplit("/", 1)[-1],
        operado_por=usuario,
        total_registros=total,
        registros_ok=total,
    )
    return importacao, conteudo
