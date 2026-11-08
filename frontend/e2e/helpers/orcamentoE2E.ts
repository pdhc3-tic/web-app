/**
 * Prelúdio Python das fixtures de E2E que mexem no orçamento (#399).
 *
 * Depois da #384/#385/#386 o saldo mora no `BudgetPool` (um por rubrica e
 * local), o limite no `SpendingLimit` (por pessoa, rubrica e período) e cada
 * movimento no ledger (`BudgetTransaction`/`BudgetTransfer`), que é imutável
 * por trigger. A fixture não consegue mais criar uma verba "marcada" só dela
 * nem apagar o que o teste lançou pelo caminho comum.
 *
 * Por isso a fixture:
 * 1. `fotografar(chave)` antes de mexer: guarda os valores de todos os pools e
 *    limites e o último id do ledger, das transferências e dos alertas, num
 *    arquivo do container (sobrevive a um run interrompido);
 * 2. ajusta o que precisa com `definir_pool` e `definir_limite`;
 * 3. no teardown, ANTES de apagar as próprias demandas e atividades (o ledger
 *    referencia a atividade com PROTECT), `restaurar(chave)`:
 *    apaga só as linhas de ledger, transferência e alerta criadas depois da
 *    fotografia, remove pools e limites que não existiam e devolve os valores.
 *
 * A remoção roda com `session_replication_role = replica`, que desliga o
 * trigger de imutabilidade só nessa transação. Exige o usuário `postgres`
 * (superusuário), o mesmo que as fixtures já usam por causa do RLS. Os specs
 * rodam em série num único worker, então uma restauração nunca apaga
 * lançamentos de outro spec. Não rodar E2E com teste manual em andamento.
 */
export const ORCAMENTO_E2E_PY = `
import json as _json
import os as _os
from decimal import Decimal as _D
from django.db import connection as _conn, transaction as _tx
from django.db.models import Max as _Max
from apps.sgp.budget import limites as _limites
from apps.sgp.budget.models import (
    BudgetAlert as _Alerta, BudgetPool as _Pool, BudgetTransaction as _Lancamento,
    BudgetTransfer as _Transferencia, SpendingLimit as _Limite,
)


def _arquivo_da_foto(chave):
    return f"/tmp/e2e-orcamento-{chave}.json"


def _ultimo(modelo):
    return modelo.objects.aggregate(m=_Max("pk"))["m"] or 0


def fotografar(chave):
    """Guarda o orçamento antes da fixture mexer nele. Se já houver foto (run
    interrompido), restaura antes, para fotografar o estado limpo."""
    restaurar(chave)
    foto = {
        "lancamento": _ultimo(_Lancamento),
        "transferencia": _ultimo(_Transferencia),
        "alerta": _ultimo(_Alerta),
        "pools": {
            str(p.pk): [str(p.valor_alocado), str(p.valor_comprometido), str(p.valor_executado), p.reserva_ugp]
            for p in _Pool.objects.all()
        },
        "limites": {
            str(l.pk): [str(l.valor_limite), str(l.valor_comprometido), str(l.valor_executado)]
            for l in _Limite.objects.all()
        },
    }
    with open(_arquivo_da_foto(chave), "w") as f:
        _json.dump(foto, f)


def restaurar(chave):
    """Desfaz tudo o que o orçamento sofreu desde \`fotografar(chave)\`."""
    caminho = _arquivo_da_foto(chave)
    if not _os.path.exists(caminho):
        return
    with open(caminho) as f:
        foto = _json.load(f)
    with _tx.atomic():
        with _conn.cursor() as cursor:
            cursor.execute("SET LOCAL session_replication_role = replica")
        lancamentos = _Lancamento.objects.filter(pk__gt=foto["lancamento"])
        lancamentos._raw_delete(lancamentos.db)
        transferencias = _Transferencia.objects.filter(pk__gt=foto["transferencia"])
        transferencias._raw_delete(transferencias.db)
        alertas = _Alerta.objects.filter(pk__gt=foto["alerta"])
        alertas._raw_delete(alertas.db)
        limites_novos = _Limite.objects.exclude(pk__in=[int(pk) for pk in foto["limites"]])
        limites_novos._raw_delete(limites_novos.db)
        pools_novos = _Pool.objects.exclude(pk__in=[int(pk) for pk in foto["pools"]])
        pools_novos._raw_delete(pools_novos.db)
        for pk, (alocado, comprometido, executado, reserva_ugp) in foto["pools"].items():
            _Pool.objects.filter(pk=int(pk)).update(
                valor_alocado=_D(alocado), valor_comprometido=_D(comprometido),
                valor_executado=_D(executado), reserva_ugp=reserva_ugp,
            )
        for pk, (limite, comprometido, executado) in foto["limites"].items():
            _Limite.objects.filter(pk=int(pk)).update(
                valor_limite=_D(limite), valor_comprometido=_D(comprometido), valor_executado=_D(executado),
            )
    _os.remove(caminho)


def definir_pool(rubrica, nivel, valor, *, territorio_id=None, estado=None, comprometido="0", executado="0"):
    """O pool da rubrica no local, criado se não existir, com o alocado dado e o
    comprometido/executado zerados (ou nos valores dados). Some na restauração."""
    pool, _ = _Pool.objects.get_or_create(
        rubrica=rubrica, nivel=nivel, estado=estado, territorio_id=territorio_id,
        defaults={"valor_alocado": _D(valor)},
    )
    _Pool.objects.filter(pk=pool.pk).update(
        valor_alocado=_D(valor), valor_comprometido=_D(comprometido), valor_executado=_D(executado),
    )
    pool.refresh_from_db()
    return pool


def definir_limite(user, rubrica, valor):
    """A linha individual do período vigente, com o limite dado e nada usado.
    Sobrescrita explícita (\`herdado=False\`), por isso leva justificativa."""
    inicio, fim = _limites.periodo_de(_limites.hoje())
    linha = (
        _Limite.objects.filter(
            escopo="individual", user=user, rubrica=rubrica,
            periodo_inicio__lte=_limites.hoje(), periodo_fim__gte=_limites.hoje(),
        ).order_by("-periodo_inicio").first()
    )
    if linha is None:
        linha = _Limite.objects.create(
            escopo="individual", user=user, rubrica=rubrica, periodo_inicio=inicio, periodo_fim=fim,
            territorio_id=_limites.territorio_do_usuario(user.pk), valor_limite=_D(valor),
            justificativa="Fixture E2E.",
        )
    _Limite.objects.filter(pk=linha.pk).update(
        valor_limite=_D(valor), valor_comprometido=_D("0"), valor_executado=_D("0"),
    )
    linha.refresh_from_db()
    return linha
`;
