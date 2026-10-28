"""Preenche o estado da reserva das solicitações a partir da trilha do limite
individual no AuditLog e aborta se o resultado não fechar com o
`valor_comprometido` de cada limite. Recalcula tudo a cada execução, então
rodar de novo dá o mesmo resultado."""
from collections import defaultdict
from decimal import Decimal

from django.db import migrations

ZERO = Decimal("0")
ENTIDADE_LIMITE = "DemandIndividualLimit"
# `aumento_limite` e `remanejamento_emergencial` usam a mesma entidade, mas não
# movem a reserva de uma solicitação.
EVENTOS_DA_RESERVA = ["reserva", "ajuste", "liberacao", "execucao"]


def reconstruir_estado(AuditLog) -> dict[int, tuple[Decimal, Decimal | None]]:
    """{pk da solicitação: (valor_reservado, valor_executado)}, reproduzindo os
    eventos na ordem em que aconteceram."""
    estado = {}
    eventos = (
        AuditLog.objects.filter(entidade=ENTIDADE_LIMITE, acao__in=EVENTOS_DA_RESERVA)
        .order_by("timestamp", "id")
        .values_list("id", "entidade_id", "acao", "valores_novos")
    )
    for evento_id, entidade_id, acao, novos in eventos.iterator():
        if not entidade_id.isdigit():
            continue
        pk = int(entidade_id)
        reservado, executado = estado.get(pk, (ZERO, None))
        if acao == "liberacao":
            reservado = ZERO
        else:
            chave = "valor_pago" if acao == "execucao" else "valor"
            if (novos or {}).get(chave) is None:
                raise RuntimeError(f"Evento #{evento_id} ({acao}) do AuditLog sem `{chave}` em valores_novos.")
            if acao == "execucao":
                executado = Decimal(novos[chave])
            else:
                reservado = Decimal(novos[chave])
        estado[pk] = (reservado, executado)
    return estado


def divergencias(DemandRequest, DemandIndividualLimit) -> list[str]:
    reservado = defaultdict(lambda: ZERO)
    ativas = DemandRequest.objects.filter(valor_reservado__gt=0, valor_executado__isnull=True)
    for solicitante_id, rubrica_id, valor in ativas.values_list("demanda__solicitante", "rubrica", "valor_reservado"):
        reservado[(solicitante_id, rubrica_id)] += valor

    mensagens = []
    limites = DemandIndividualLimit.objects.order_by("pk").values_list(
        "pk", "solicitante", "rubrica", "valor_comprometido",
    )
    for pk, solicitante_id, rubrica_id, comprometido in limites:
        esperado = reservado.pop((solicitante_id, rubrica_id), ZERO)
        if comprometido != esperado:
            mensagens.append(
                f"Limite #{pk}: valor_comprometido={comprometido}, reservas ativas somam {esperado}."
            )
    for (solicitante_id, rubrica_id), valor in sorted(reservado.items()):
        mensagens.append(
            f"Solicitante #{solicitante_id}, rubrica #{rubrica_id}: reservas ativas somam {valor} sem limite individual."
        )
    return mensagens


def preencher(apps, schema_editor):
    AuditLog = apps.get_model("core", "AuditLog")
    DemandRequest = apps.get_model("sgd", "DemandRequest")
    DemandIndividualLimit = apps.get_model("sgd", "DemandIndividualLimit")

    estado = reconstruir_estado(AuditLog)
    DemandRequest.objects.update(valor_reservado=ZERO, valor_executado=None)
    # Solicitação removida na edição tem eventos, mas não existe mais.
    existentes = DemandRequest.objects.filter(pk__in=list(estado)).order_by("pk").values_list("pk", flat=True)
    DemandRequest.objects.bulk_update(
        [DemandRequest(pk=pk, valor_reservado=estado[pk][0], valor_executado=estado[pk][1]) for pk in existentes],
        ["valor_reservado", "valor_executado"],
        batch_size=500,
    )

    encontradas = divergencias(DemandRequest, DemandIndividualLimit)
    if encontradas:
        raise RuntimeError(
            "O estado da reserva reconstruído do AuditLog não fecha com o comprometido dos limites "
            "individuais. Corrija os limites antes de migrar:\n" + "\n".join(encontradas)
        )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0021_seed_budget_alert_limiares"),
        ("sgd", "0013_demandrequest_estado_da_reserva"),
    ]

    operations = [
        migrations.RunPython(preencher, migrations.RunPython.noop),
    ]
