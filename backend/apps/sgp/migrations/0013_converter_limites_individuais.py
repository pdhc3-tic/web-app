"""Converte cada limite individual em sobrescrita do período corrente, preservando comprometido e
executado, e abre o ledger de cada um: o valor do limite, o que já foi executado e uma linha por
reserva ativa, que é por onde a liberação e a execução acham a linha do limite."""
import calendar
from datetime import date
from decimal import Decimal

from django.db import migrations
from django.utils import timezone

ZERO = Decimal("0")
JUSTIFICATIVA = "Convertido do limite individual do SGD."
ABERTURA = "Saldo de abertura da conversão do limite individual."
MESES = {"mensal": 1, "trimestral": 3, "semestral": 6}


def _periodo_corrente(SystemConfig) -> tuple[date, date]:
    config = SystemConfig.objects.filter(chave="budget_limit_period").first()
    periodicidade = config.valor if config else "trimestral"
    if periodicidade == "vigencia":
        return date(2000, 1, 1), date(2099, 12, 31)
    hoje = timezone.localdate()
    meses = MESES.get(periodicidade, 3)
    primeiro = ((hoje.month - 1) // meses) * meses + 1
    ultimo = primeiro + meses - 1
    return date(hoje.year, primeiro, 1), date(hoje.year, ultimo, calendar.monthrange(hoje.year, ultimo)[1])


def _abrir_ledger(limite, novo, BudgetTransaction, DemandRequest) -> None:
    def lancar(tipo, valor, *, demanda_id=None, activity_id=None, justificativa=ABERTURA):
        BudgetTransaction.objects.create(
            spending_limit=novo, tipo=tipo, valor=valor, demanda_id=demanda_id, activity_id=activity_id,
            justificativa=justificativa, criado_por_id=limite.criado_por_id,
        )

    lancar("aumento_limite", limite.valor_limite)
    if limite.valor_executado > ZERO:
        lancar("reserva", limite.valor_executado)
        lancar("execucao", limite.valor_executado)
    reservas = DemandRequest.objects.filter(
        demanda__solicitante_id=limite.solicitante_id, rubrica_id=limite.rubrica_id,
        valor_reservado__gt=ZERO, valor_executado__isnull=True,
    ).values_list("pk", "valor_reservado", "valor_excedente", "demanda__activity_id")
    for pk, reservado, excedente, activity_id in reservas.order_by("pk"):
        no_limite = reservado - excedente
        if no_limite > ZERO:
            lancar(
                "reserva", no_limite, demanda_id=str(pk), activity_id=activity_id,
                justificativa=f"Reserva SGD — solicitação #{pk}.",
            )


def converter(apps, schema_editor):
    DemandIndividualLimit = apps.get_model("sgd", "DemandIndividualLimit")
    DemandRequest = apps.get_model("sgd", "DemandRequest")
    SpendingLimit = apps.get_model("sgp", "SpendingLimit")
    BudgetTransaction = apps.get_model("sgp", "BudgetTransaction")
    SystemConfig = apps.get_model("core", "SystemConfig")
    UserProfile = apps.get_model("core", "UserProfile")

    inicio, fim = _periodo_corrente(SystemConfig)
    for limite in DemandIndividualLimit.objects.order_by("pk"):
        territorio_id = (
            UserProfile.objects
            .filter(
                user_id=limite.solicitante_id, territorio__isnull=False,
                perfil__slug__in=["adt-acr", "articulador-estadual"],
            )
            .order_by("pk").values_list("territorio_id", flat=True).first()
        )
        novo = SpendingLimit.objects.create(
            escopo="individual", user_id=limite.solicitante_id, rubrica_id=limite.rubrica_id,
            territorio_id=territorio_id, valor_limite=limite.valor_limite,
            valor_comprometido=limite.valor_comprometido, valor_executado=limite.valor_executado,
            justificativa=JUSTIFICATIVA, periodo_inicio=inicio, periodo_fim=fim,
            criado_por_id=limite.criado_por_id,
        )
        _abrir_ledger(limite, novo, BudgetTransaction, DemandRequest)


def desconverter(apps, schema_editor):
    """Volta a uma linha por solicitante e rubrica: a mais recente dá o valor do limite, e os saldos de
    todos os períodos se somam. Os padrões por perfil não têm para onde voltar e são descartados."""
    DemandIndividualLimit = apps.get_model("sgd", "DemandIndividualLimit")
    SpendingLimit = apps.get_model("sgp", "SpendingLimit")
    BudgetTransaction = apps.get_model("sgp", "BudgetTransaction")

    grupos = {}
    for linha in SpendingLimit.objects.filter(escopo="individual").order_by("periodo_inicio", "pk"):
        grupos.setdefault((linha.user_id, linha.rubrica_id), []).append(linha)
    for (user_id, rubrica_id), linhas in grupos.items():
        # A tabela antiga só some em `sgd.0019`: revertendo antes dela, a linha ainda está lá.
        DemandIndividualLimit.objects.update_or_create(
            solicitante_id=user_id, rubrica_id=rubrica_id,
            defaults={
                "valor_limite": linhas[-1].valor_limite,
                "valor_comprometido": sum((linha.valor_comprometido for linha in linhas), ZERO),
                "valor_executado": sum((linha.valor_executado for linha in linhas), ZERO),
                "criado_por_id": linhas[-1].criado_por_id,
            },
        )
    BudgetTransaction.objects.filter(spending_limit__isnull=False).delete()
    SpendingLimit.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0023_seed_budget_limites'),
        ('sgd', '0018_preencher_totais_das_demandas'),
        ('sgp', '0012_spendinglimit_esquema'),
    ]

    operations = [
        migrations.RunPython(converter, desconverter),
    ]
