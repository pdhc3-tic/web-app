"""Diárias nos moldes do serviço público federal (Lei 8.112/1990, art. 58; Decreto 5.992/2006):
faixa de destino, valor vigente, contagem com meia diária e adicional de embarque."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.core.models.system_config import SystemConfig, TipoConfiguracao
from apps.core.services.audit import log_audit
from apps.core.utils import get_config
from apps.sgd.constants import CODIGOS_IBGE_CAPITAIS
from apps.sgd.exceptions import RegraDeNegocio
from apps.sgd.models.demand_request import DemandRequest
from apps.sgd.models.diarias import (
    CategoriaBeneficiario,
    EnquadramentoFaixaDiaria,
    FaixaDestinoDiaria,
    PadraoFaixa,
    TabelaDiaria,
)

MEIA = Decimal("0.5")
INTEIRA = Decimal("1")

REGRA_INTEIRA_POR_PERNOITE = "sgd_diaria_regra_inteira_por_pernoite"
REGRA_MEIA_NO_RETORNO = "sgd_diaria_regra_meia_no_retorno"
REGRA_MEIA_SEM_PERNOITE = "sgd_diaria_regra_meia_sem_pernoite"
REGRA_MEIA_HOSPEDAGEM_CUSTEADA = "sgd_diaria_regra_meia_hospedagem_custeada"
ADICIONAL_EMBARQUE_ATIVO = "sgd_diaria_adicional_embarque_ativo"
ADICIONAL_EMBARQUE_VALOR = "sgd_diaria_adicional_embarque_valor"

# Campo da API -> chave do SystemConfig. Super Admin e FGD editam só estas chaves.
PARAMETROS = {
    "regra_inteira_por_pernoite": REGRA_INTEIRA_POR_PERNOITE,
    "regra_meia_no_retorno": REGRA_MEIA_NO_RETORNO,
    "regra_meia_sem_pernoite": REGRA_MEIA_SEM_PERNOITE,
    "regra_meia_hospedagem_custeada": REGRA_MEIA_HOSPEDAGEM_CUSTEADA,
    "adicional_embarque_ativo": ADICIONAL_EMBARQUE_ATIVO,
    "adicional_embarque_valor": ADICIONAL_EMBARQUE_VALOR,
}


def _regra(chave: str, padrao: bool = True) -> bool:
    # Parâmetro de regra apagado do Core volta ao padrão federal, que é ligado.
    valor = get_config(chave, padrao)
    if isinstance(valor, str):
        return valor.strip().lower() in ("true", "1", "sim")
    return bool(valor)


def resolver_faixa(municipio) -> FaixaDestinoDiaria:
    """Enquadramento explícito do município; sem ele, "demais capitais" para capital e
    "demais localidades" para o resto."""
    enquadramento = (
        EnquadramentoFaixaDiaria.objects.select_related("faixa")
        .filter(codigo_ibge=municipio.codigo_ibge, faixa__ativo=True)
        .first()
    )
    if enquadramento is not None:
        return enquadramento.faixa
    padrao = PadraoFaixa.CAPITAIS if municipio.codigo_ibge in CODIGOS_IBGE_CAPITAIS else PadraoFaixa.DEMAIS
    faixa = FaixaDestinoDiaria.objects.filter(padrao=padrao, ativo=True).first()
    if faixa is None:
        raise RegraDeNegocio(
            f"Nenhuma faixa de destino ativa recebe '{PadraoFaixa(padrao).label}'. "
            "Contate a FGD ou o Super Admin.",
            campo="municipio_destino_id",
        )
    return faixa


def _vigentes(faixa, data: date, categoria: str):
    return TabelaDiaria.objects.filter(
        faixa_destino=faixa, categoria_beneficiario=categoria, vigencia_inicio__lte=data,
    ).filter(Q(vigencia_fim__isnull=True) | Q(vigencia_fim__gte=data))


def valor_vigente(faixa, data: date, categoria: str = CategoriaBeneficiario.PADRAO) -> TabelaDiaria:
    """Início e fim da vigência são inclusivos."""
    linha = _vigentes(faixa, data, categoria).order_by("-vigencia_inicio", "-pk").first()
    if linha is None:
        raise RegraDeNegocio(
            f"Sem valor de diária vigente para a faixa '{faixa.nome}' em {data.strftime('%d/%m/%Y')}. "
            "Contate a FGD ou o Super Admin.",
            campo="valor_por_diaria",
        )
    return linha


def contar_diarias(inicio: date, fim: date, hospedagem_custeada: bool = False) -> Decimal:
    """Ex.: saída na segunda e retorno na quarta = 2 pernoites + meia diária = 2,5."""
    return _contar(inicio, fim, hospedagem_custeada).quantize(Decimal("0.1"))


def _contar(inicio: date, fim: date, hospedagem_custeada: bool) -> Decimal:
    pernoites = (fim - inicio).days
    if not _regra(REGRA_INTEIRA_POR_PERNOITE):
        return Decimal(pernoites + 1)
    if pernoites == 0:
        return MEIA if _regra(REGRA_MEIA_SEM_PERNOITE) else INTEIRA
    por_pernoite = MEIA if hospedagem_custeada and _regra(REGRA_MEIA_HOSPEDAGEM_CUSTEADA) else INTEIRA
    retorno = MEIA if _regra(REGRA_MEIA_NO_RETORNO) else INTEIRA
    return pernoites * por_pernoite + retorno


def adicional_embarque() -> Decimal:
    """O que entra no total: zero com o adicional desligado."""
    if not _regra(ADICIONAL_EMBARQUE_ATIVO, padrao=False):
        return Decimal("0.00")
    return adicional_embarque_configurado()


def adicional_embarque_configurado() -> Decimal:
    try:
        valor = Decimal(str(get_config(ADICIONAL_EMBARQUE_VALOR, "0")).strip())
    except (InvalidOperation, ValueError):
        raise RegraDeNegocio(
            f"Valor do adicional de embarque inválido — contate o Super Admin ({ADICIONAL_EMBARQUE_VALOR}).",
            campo="adicional_embarque",
        )
    return max(valor, Decimal("0")).quantize(Decimal("0.01"))


@dataclass
class CalculoDiarias:
    faixa: FaixaDestinoDiaria
    tabela: TabelaDiaria
    numero: Decimal
    valor_por_diaria: Decimal
    adicional_embarque: Decimal
    valor_total: Decimal


def calcular(*, municipio, data_inicio: date, data_fim: date, hospedagem_custeada: bool = False) -> CalculoDiarias:
    faixa = resolver_faixa(municipio)
    tabela = valor_vigente(faixa, data_inicio)
    numero = contar_diarias(data_inicio, data_fim, hospedagem_custeada)
    adicional = adicional_embarque()
    total = (numero * tabela.valor + adicional).quantize(Decimal("0.01"))
    return CalculoDiarias(
        faixa=faixa, tabela=tabela, numero=numero, valor_por_diaria=tabela.valor,
        adicional_embarque=adicional, valor_total=total,
    )


# --- Parâmetros do Core ---------------------------------------------------------------


def ler_parametros() -> dict:
    return {
        "regra_inteira_por_pernoite": _regra(REGRA_INTEIRA_POR_PERNOITE),
        "regra_meia_no_retorno": _regra(REGRA_MEIA_NO_RETORNO),
        "regra_meia_sem_pernoite": _regra(REGRA_MEIA_SEM_PERNOITE),
        "regra_meia_hospedagem_custeada": _regra(REGRA_MEIA_HOSPEDAGEM_CUSTEADA),
        "adicional_embarque_ativo": _regra(ADICIONAL_EMBARQUE_ATIVO, padrao=False),
        "adicional_embarque_valor": adicional_embarque_configurado(),
    }


@transaction.atomic
def atualizar_parametros(dados: dict, *, user) -> dict:
    """Grava no SystemConfig do Core; o signal do Core audita a mudança e limpa o cache."""
    for campo, valor in dados.items():
        chave = PARAMETROS[campo]
        if isinstance(valor, bool):
            texto, tipo = str(valor), TipoConfiguracao.BOOLEAN
        else:
            texto, tipo = str(Decimal(valor).quantize(Decimal("0.01"))), TipoConfiguracao.STRING
        config = SystemConfig.objects.select_for_update().filter(chave=chave).first()
        if config is None:
            SystemConfig.objects.create(chave=chave, valor=texto, tipo=tipo, atualizado_por=user)
            log_audit(
                user=user, acao="system_config.created", modulo="core", entidade="SystemConfig",
                entidade_id=chave, valores_novos={"valor": texto},
            )
        elif config.valor != texto:
            config.valor = texto
            config.atualizado_por = user
            config.save(update_fields=["valor", "atualizado_por", "atualizado_em"])
    return ler_parametros()


# --- Manutenção da tabela -------------------------------------------------------------


def dados_auditoria(linha: TabelaDiaria) -> dict:
    return {
        "faixa_destino": linha.faixa_destino_id,
        "categoria_beneficiario": linha.categoria_beneficiario,
        "vigencia_inicio": linha.vigencia_inicio.isoformat(),
        "vigencia_fim": linha.vigencia_fim.isoformat() if linha.vigencia_fim else None,
        "valor": str(linha.valor),
        "origem": linha.origem,
    }


def _exigir_sem_sobreposicao(*, faixa, categoria, inicio: date, fim: date | None, ignorar=()) -> None:
    conflito = TabelaDiaria.objects.filter(faixa_destino=faixa, categoria_beneficiario=categoria).exclude(
        pk__in=[pk for pk in ignorar if pk],
    ).filter(Q(vigencia_fim__isnull=True) | Q(vigencia_fim__gte=inicio))
    if fim is not None:
        conflito = conflito.filter(vigencia_inicio__lte=fim)
    existente = conflito.order_by("vigencia_inicio").first()
    if existente is not None:
        fim_txt = existente.vigencia_fim.strftime("%d/%m/%Y") if existente.vigencia_fim else "sem fim"
        raise RegraDeNegocio(
            f"A vigência se sobrepõe à de {existente.vigencia_inicio.strftime('%d/%m/%Y')} a {fim_txt} "
            f"(R$ {existente.valor}) desta faixa. Edite aquele valor para criar uma nova vigência.",
            campo="vigencia_inicio",
        )


def _travar_faixa(faixa) -> None:
    # Serializa criações concorrentes na mesma faixa para a checagem de sobreposição valer.
    FaixaDestinoDiaria.objects.select_for_update().filter(pk=faixa.pk).first()


@transaction.atomic
def criar_valor(*, faixa, categoria, inicio, fim, valor, origem, user, request=None) -> TabelaDiaria:
    _travar_faixa(faixa)
    _exigir_sem_sobreposicao(faixa=faixa, categoria=categoria, inicio=inicio, fim=fim)
    linha = TabelaDiaria.objects.create(
        faixa_destino=faixa, categoria_beneficiario=categoria, vigencia_inicio=inicio, vigencia_fim=fim,
        valor=valor, origem=origem, criado_por=user if getattr(user, "is_authenticated", False) else None,
    )
    log_audit(
        user=user, acao="tabela_diaria.criado", modulo="sgd", entidade="TabelaDiaria", entidade_id=linha.pk,
        valores_novos=dados_auditoria(linha), request=request,
    )
    return linha


@transaction.atomic
def registrar_nova_vigencia(*, atual: TabelaDiaria, valor, inicio: date, origem, user, request=None) -> TabelaDiaria:
    """Editar um valor não sobrescreve: a vigência atual termina na véspera de `inicio` e
    uma nova linha começa em `inicio`, até onde a atual iria."""
    _travar_faixa(atual.faixa_destino)
    atual = TabelaDiaria.objects.select_for_update().get(pk=atual.pk)
    if inicio <= atual.vigencia_inicio:
        raise RegraDeNegocio(
            f"A nova vigência precisa começar depois de {atual.vigencia_inicio.strftime('%d/%m/%Y')}, "
            "início da vigência editada.",
            campo="vigencia_inicio",
        )
    if atual.vigencia_fim is not None and inicio > atual.vigencia_fim:
        raise RegraDeNegocio(
            f"A vigência editada terminou em {atual.vigencia_fim.strftime('%d/%m/%Y')}. "
            "Cadastre um novo valor para o período seguinte.",
            campo="vigencia_inicio",
        )
    anteriores = dados_auditoria(atual)
    fim_original = atual.vigencia_fim
    atual.vigencia_fim = inicio - timedelta(days=1)
    atual.save(update_fields=["vigencia_fim"])
    _exigir_sem_sobreposicao(
        faixa=atual.faixa_destino, categoria=atual.categoria_beneficiario, inicio=inicio, fim=fim_original,
        ignorar=[atual.pk],
    )
    nova = TabelaDiaria.objects.create(
        faixa_destino=atual.faixa_destino, categoria_beneficiario=atual.categoria_beneficiario,
        vigencia_inicio=inicio, vigencia_fim=fim_original, valor=valor, origem=origem,
        criado_por=user if getattr(user, "is_authenticated", False) else None,
    )
    log_audit(
        user=user, acao="tabela_diaria.nova_vigencia", modulo="sgd", entidade="TabelaDiaria", entidade_id=nova.pk,
        valores_anteriores={"id": atual.pk, **anteriores},
        valores_novos={
            "id": nova.pk, **dados_auditoria(nova),
            "vigencia_anterior_encerrada_em": atual.vigencia_fim.isoformat(),
        },
        request=request,
    )
    return nova


@transaction.atomic
def excluir_valor(*, linha: TabelaDiaria, user, request=None) -> None:
    """Só sai da tabela o valor que ainda não vigorou e que nenhuma solicitação usou; o resto
    é histórico. Se a linha veio de uma edição, a vigência anterior volta a cobrir o período."""
    _travar_faixa(linha.faixa_destino)
    linha = TabelaDiaria.objects.select_for_update().get(pk=linha.pk)
    hoje = timezone.localdate()
    if linha.vigencia_inicio <= hoje:
        raise RegraDeNegocio(
            f"A vigência começou em {linha.vigencia_inicio.strftime('%d/%m/%Y')} e faz parte do histórico. "
            "Edite o valor para criar uma nova vigência.",
            campo="vigencia_inicio",
        )
    if DemandRequest.objects.filter(campos_json__tabela_diaria_id=linha.pk).exists():
        raise RegraDeNegocio(
            "Este valor já foi usado em solicitação de diária e não pode ser removido. "
            "Edite-o para criar uma nova vigência.",
            campo="tabela_diaria",
        )
    anterior = TabelaDiaria.objects.select_for_update().filter(
        faixa_destino=linha.faixa_destino, categoria_beneficiario=linha.categoria_beneficiario,
        vigencia_fim=linha.vigencia_inicio - timedelta(days=1),
    ).first()
    anteriores = {"id": linha.pk, **dados_auditoria(linha)}
    novos = {}
    if anterior is not None:
        anterior.vigencia_fim = linha.vigencia_fim
        anterior.save(update_fields=["vigencia_fim"])
        novos["vigencia_reaberta"] = {"id": anterior.pk, **dados_auditoria(anterior)}
    pk = linha.pk
    linha.delete()
    log_audit(
        user=user, acao="tabela_diaria.removido", modulo="sgd", entidade="TabelaDiaria", entidade_id=pk,
        valores_anteriores=anteriores, valores_novos=novos, request=request,
    )
