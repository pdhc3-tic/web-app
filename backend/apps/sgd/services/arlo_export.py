"""Exportação das demandas autorizadas para o Arlo (SGD-RF31)."""
from decimal import Decimal
from uuid import uuid4

from django.db import transaction

from apps.core.storage import get_storage
from apps.sgd.models.arlo_import import ArloImport
from apps.sgd.models.demand import Demand
from apps.sgd.models.demand_request import DemandRequest
from apps.sgd.services.arlo_mapping import formatar_valor, obter_mapeamento
from apps.sgp.models import ExportJob
from apps.sgp.services.exportacao import gerar_arquivo

CONTENT_TYPE_CSV = "text/csv"

# Linha do preview quando ainda não há demanda autorizada para exportar.
LINHA_DE_EXEMPLO = {
    "demanda_id": 123,
    "solicitacao_id": 456,
    "titulo": "Diárias para a oficina de manejo da caatinga",
    "meta": "1 - Assistência técnica às famílias",
    "submeta": "1.1 - Visitas e oficinas",
    "acao": "1.1.1 - Oficina de manejo",
    "indicador": "IND-01 - Famílias atendidas",
    "atividade": "Oficina de manejo da caatinga",
    "rubrica": "Diárias",
    "solicitante": "Fulano de Tal",
    "valor_estimado": Decimal("1500.00"),
    "valor_autorizado": Decimal("1200.00"),
}


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


def gerar_csv(demandas=None, mapeamento=None) -> tuple[bytes, int]:
    """Uma linha por solicitação (rubrica) — é a granularidade do pagamento."""
    colunas = (mapeamento or obter_mapeamento())["exportacao"]
    columns = [(item["campo"], item["coluna"]) for item in colunas]
    formatos = {item["campo"]: item["formato"] for item in colunas}
    rows = [
        {campo: formatar_valor(valor, formatos.get(campo)) for campo, valor in _linha(demand, solicitacao).items()}
        for demand in (demandas_autorizadas() if demandas is None else demandas)
        for solicitacao in sorted(demand.solicitacoes.all(), key=lambda s: (s.rubrica_id, s.pk))
    ]
    return gerar_arquivo(columns, rows, ExportJob.Formato.CSV, "Arlo"), len(rows)


def preview() -> dict:
    """Cabeçalho e uma linha da exportação com o mapeamento vigente, formatados
    como no CSV. Usa a primeira solicitação de demanda autorizada ou, sem
    nenhuma, `LINHA_DE_EXEMPLO`."""
    colunas = obter_mapeamento()["exportacao"]
    solicitacao = (
        DemandRequest.objects.filter(demanda__status="autorizada")
        .select_related(
            "rubrica", "demanda__solicitante", "demanda__activity__acao__meta",
            "demanda__activity__acao__submeta", "demanda__activity__acao__indicador",
        )
        .order_by("demanda_id", "rubrica_id", "pk")
        .first()
    )
    valores = _linha(solicitacao.demanda, solicitacao) if solicitacao else LINHA_DE_EXEMPLO
    return {
        "colunas": [item["coluna"] for item in colunas],
        "linha": [str(formatar_valor(valores.get(item["campo"]), item["formato"])) for item in colunas],
        "exemplo": solicitacao is None,
    }


@transaction.atomic
def exportar(*, usuario) -> tuple[ArloImport, bytes]:
    mapeamento = obter_mapeamento()
    conteudo, total = gerar_csv(mapeamento=mapeamento)
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
        mapeamento_snapshot=mapeamento,
    )
    return importacao, conteudo
