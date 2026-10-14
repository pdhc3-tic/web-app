"""Importação do retorno de pagamento do Arlo (SGD-RF32, RF24).

Cada linha da planilha é processada numa transação própria: uma linha com
erro vira entrada em `erros_json` e não impede as válidas do mesmo arquivo.
"""
import csv
import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO, StringIO
from urllib.parse import urlparse

from django.db import transaction
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.core.models.audit_log import AuditLog
from apps.core.signals.audit import clear_audit_context, get_audit_context, set_audit_context
from apps.core.storage import StorageObjectNotFound, get_storage
from apps.sgd.models.approval_step import ApprovalStep
from apps.sgd.models.arlo_import import ArloImport
from apps.sgd.models.demand import Demand
from apps.sgd.models.demand_document import DemandDocument
from apps.sgd.services import balance as balance_service
from apps.sgd.services import notifications as notifications_service
from apps.sgd.services.approval import TransicaoInvalidaError, aplicar_transicao
from apps.sgd.services.arlo_mapping import CAMPOS_IMPORTACAO_OBRIGATORIOS, obter_mapeamento
from apps.sgp.models import GlosaRisk
from apps.sgp.services.apuracao import recalcular_valor_executado

logger = logging.getLogger(__name__)

STATUS_PAGAVEIS = {"autorizada", "em_atendimento"}
FORMATOS_DATA = ("%Y-%m-%d", "%d/%m/%Y")


class LinhaInvalida(Exception):
    def __init__(self, erro: str, campo: str | None = None):
        super().__init__(erro)
        self.erro = erro
        self.campo = campo


class ArquivoInvalido(Exception):
    pass


def _ler_linhas(conteudo: bytes, nome: str) -> tuple[list[str], list[dict]]:
    if nome.lower().endswith(".xlsx"):
        return _ler_xlsx(conteudo)
    texto = conteudo.decode("utf-8-sig")
    try:
        dialect = csv.Sniffer().sniff(texto[:2048], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(StringIO(texto), dialect=dialect)
    return list(reader.fieldnames or []), [dict(linha) for linha in reader]


def _ler_xlsx(conteudo: bytes) -> tuple[list[str], list[dict]]:
    from openpyxl import load_workbook

    planilha = load_workbook(BytesIO(conteudo), read_only=True, data_only=True).active
    linhas = planilha.iter_rows(values_only=True)
    cabecalho = [str(c).strip() if c is not None else "" for c in next(linhas, [])]
    return cabecalho, [
        {cabecalho[i]: ("" if v is None else v) for i, v in enumerate(linha) if i < len(cabecalho)}
        for linha in linhas
    ]


def _valor(linha: dict, colunas: dict, campo: str):
    coluna = colunas.get(campo)
    bruto = linha.get(coluna) if coluna else None
    if isinstance(bruto, str):
        bruto = bruto.strip()
    return "" if bruto is None else bruto


def _parse_valor(bruto) -> Decimal:
    if isinstance(bruto, (int, float, Decimal)):
        texto = str(bruto)
    else:
        texto = str(bruto).replace("R$", "").strip()
        if "," in texto:
            texto = texto.replace(".", "").replace(",", ".")
    try:
        valor = Decimal(texto)
    except InvalidOperation:
        raise LinhaInvalida(f"Valor pago em formato inválido: '{bruto}'.", "valor_pago")
    if not valor.is_finite() or valor < 0:
        raise LinhaInvalida(f"Valor pago inválido: '{bruto}'.", "valor_pago")
    return valor.quantize(Decimal("0.01"))


def _parse_data(bruto) -> date:
    if isinstance(bruto, datetime):
        return bruto.date()
    if isinstance(bruto, date):
        return bruto
    for formato in FORMATOS_DATA:
        try:
            return datetime.strptime(str(bruto), formato).date()
        except ValueError:
            continue
    raise LinhaInvalida(f"Data do pagamento em formato inválido: '{bruto}'.", "data_pagamento")


def _parse_inteiro(bruto, campo: str) -> int:
    try:
        return int(Decimal(str(bruto)))
    except (InvalidOperation, ValueError):
        raise LinhaInvalida(f"'{bruto}' não é um identificador válido.", campo)


def _validar_comprovante(bruto) -> str:
    if not bruto:
        return ""
    parsed = urlparse(str(bruto))
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise LinhaInvalida("Comprovante deve ser uma URL http(s).", "comprovante")
    return str(bruto)


def _localizar_solicitacao(demand, bruto_solicitacao):
    solicitacoes = list(demand.solicitacoes.select_related("rubrica").order_by("rubrica_id", "pk"))
    if bruto_solicitacao != "":
        pk = _parse_inteiro(bruto_solicitacao, "solicitacao_id")
        for solicitacao in solicitacoes:
            if solicitacao.pk == pk:
                return solicitacao, solicitacoes
        raise LinhaInvalida(f"Solicitação #{pk} não pertence à demanda #{demand.pk}.", "solicitacao_id")
    if len(solicitacoes) != 1:
        raise LinhaInvalida(
            f"Demanda #{demand.pk} tem {len(solicitacoes)} solicitações — informe o ID da solicitação.",
            "solicitacao_id",
        )
    return solicitacoes[0], solicitacoes


def _processar_linha(importacao, linha: dict, colunas: dict) -> None:
    for campo in CAMPOS_IMPORTACAO_OBRIGATORIOS:
        if _valor(linha, colunas, campo) == "":
            raise LinhaInvalida(f"Campo obrigatório ausente: {colunas[campo]}.", campo)

    demanda_id = _parse_inteiro(_valor(linha, colunas, "demanda_id"), "demanda_id")
    data_pagamento = _parse_data(_valor(linha, colunas, "data_pagamento"))
    valor_pago = _parse_valor(_valor(linha, colunas, "valor_pago"))
    comprovante = _validar_comprovante(_valor(linha, colunas, "comprovante"))
    numero_processo = str(_valor(linha, colunas, "numero_processo"))[:64]

    try:
        demand = Demand.objects.select_for_update().select_related("activity").get(pk=demanda_id)
    except Demand.DoesNotExist:
        raise LinhaInvalida(f"Demanda #{demanda_id} inexistente.", "demanda_id")
    if demand.status not in STATUS_PAGAVEIS:
        raise LinhaInvalida(
            f"Demanda #{demanda_id} está '{demand.status}' — só autorizadas/em atendimento recebem pagamento.",
            "demanda_id",
        )

    solicitacao, solicitacoes = _localizar_solicitacao(demand, _valor(linha, colunas, "solicitacao_id"))
    if solicitacao.valor_pago is not None:
        raise LinhaInvalida(f"Solicitação #{solicitacao.pk} já tem pagamento registrado.", "solicitacao_id")

    usuario = importacao.operado_por
    reservado = solicitacao.valor_autorizado or solicitacao.valor_estimado
    # O excedente pago acima do autorizado não é executado nos limites: fica só
    # no relatório de risco de glosa. Abaixo do autorizado, executar_duas_travas
    # devolve a diferença ao limite individual e ao pool territorial.
    try:
        balance_service.executar_duas_travas(
            demand_request=solicitacao, valor_pago=min(valor_pago, reservado), usuario=usuario,
        )
    except DRFValidationError as exc:
        raise LinhaInvalida(f"Falha ao executar no orçamento: {exc.detail}")

    if valor_pago > reservado:
        GlosaRisk.objects.create(
            demanda_id=str(demand.pk), demand_request_id=str(solicitacao.pk),
            arlo_import_id=str(importacao.pk), valor_autorizado=reservado, valor_pago=valor_pago,
            excedente=valor_pago - reservado, criado_por=usuario,
        )

    solicitacao.valor_pago = valor_pago
    solicitacao.save(update_fields=["valor_pago"])
    demand.numero_processo = numero_processo
    demand.save(update_fields=["numero_processo"])

    if comprovante:
        DemandDocument.objects.create(
            demanda=demand, arquivo_key="", arquivo_url=comprovante, tipo="comprovante",
            nome_original=urlparse(comprovante).path.rsplit("/", 1)[-1] or "comprovante",
            enviado_por=usuario,
        )

    AuditLog.objects.create(
        user=usuario, acao="arlo_pagamento", modulo="sgd", entidade="DemandRequest",
        entidade_id=str(solicitacao.pk), ip=get_audit_context()["ip"],
        valores_novos={
            "arlo_import_id": importacao.pk, "numero_processo": numero_processo,
            "data_pagamento": data_pagamento.isoformat(), "valor_pago": str(valor_pago),
            "valor_autorizado": str(reservado),
        },
    )

    if demand.status == "autorizada":
        # Mesmo efeito de `approval.atender` (SGD §5.2: solicitante notificado in-app).
        aplicar_transicao(demand, "em_atendimento")
        ApprovalStep.objects.create(demanda=demand, etapa="atendimento", responsavel=usuario, acao="atendido")
        notifications_service.notificar_em_atendimento(demand)
    if all(s.valor_pago is not None for s in solicitacoes if s.pk != solicitacao.pk):
        aplicar_transicao(demand, "concluida")
        recalcular_valor_executado([demand.activity.acao_id])
        ApprovalStep.objects.create(
            demanda=demand, etapa="atendimento", responsavel=usuario, acao="atendido",
            justificativa=f"Pagamento em {data_pagamento:%d/%m/%Y} — processo {numero_processo} (importação Arlo #{importacao.pk}).",
        )
        notifications_service.notificar_conclusao(demand)


def processar_importacao(importacao: ArloImport) -> ArloImport:
    """Lê o arquivo de retorno de `importacao` e aplica linha a linha.

    Roda fora de um request, então abre o contexto de auditoria com o usuário e
    o IP de quem enviou o arquivo — é dele que as movimentações de saldo e as
    transições de status herdam usuário/IP (SGD RNF de rastreabilidade)."""
    set_audit_context(user=importacao.operado_por, ip=importacao.ip_origem, user_agent="arlo-import")
    try:
        return _processar_importacao(importacao)
    finally:
        clear_audit_context()


def _processar_importacao(importacao: ArloImport) -> ArloImport:
    importacao.status = ArloImport.Status.PROCESSANDO
    importacao.save(update_fields=["status"])

    try:
        conteudo = get_storage().read_bytes(importacao.arquivo_key)
        cabecalho, linhas = _ler_linhas(conteudo, importacao.nome_original or importacao.arquivo_key)
        mapeamento = obter_mapeamento()
        importacao.mapeamento_snapshot = mapeamento
        importacao.save(update_fields=["mapeamento_snapshot"])
        colunas = {campo: item["coluna"] for campo, item in mapeamento["importacao"].items()}
        ausentes = [coluna for campo, coluna in colunas.items()
                    if campo in CAMPOS_IMPORTACAO_OBRIGATORIOS and coluna not in cabecalho]
        if ausentes:
            raise ArquivoInvalido(f"Colunas obrigatórias ausentes na planilha: {ausentes}.")
    except (StorageObjectNotFound, ArquivoInvalido, UnicodeDecodeError, ValueError, KeyError) as exc:
        importacao.status = ArloImport.Status.FALHOU
        importacao.erros_json = [{"linha": 1, "erro": str(exc) or "Arquivo ilegível."}]
        importacao.save(update_fields=["status", "erros_json"])
        return importacao

    erros, ok, total = [], 0, 0
    for numero, linha in enumerate(linhas, start=2):  # linha 1 é o cabeçalho
        if not any(str(v).strip() for v in linha.values() if v is not None):
            continue
        total += 1
        try:
            with transaction.atomic():
                _processar_linha(importacao, linha, colunas)
            ok += 1
        except LinhaInvalida as exc:
            erros.append({"linha": numero, "campo": exc.campo, "erro": exc.erro})
        except TransicaoInvalidaError as exc:
            erros.append({"linha": numero, "campo": None, "erro": str(exc)})
        except Exception:
            logger.exception("Erro inesperado na linha %s da importação Arlo #%s.", numero, importacao.pk)
            erros.append({"linha": numero, "campo": None, "erro": "Erro inesperado ao processar a linha."})

    importacao.total_registros = total
    importacao.registros_ok = ok
    importacao.erros_json = erros
    importacao.status = ArloImport.Status.CONCLUIDO
    importacao.save(update_fields=["total_registros", "registros_ok", "erros_json", "status"])
    return importacao
