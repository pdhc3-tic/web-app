import { execFileSync } from "node:child_process";
import path from "node:path";
import { ORCAMENTO_E2E_PY } from "./orcamentoE2E";

/**
 * Fixture do simulador de remanejamento entre pools (#402), contra o backend
 * real (`/sgp/orcamento/remanejamentos/simular/` e `/remanejamentos/`).
 *
 * Monta três pools territoriais, com os limiares do semáforo de hoje
 * (amarelo 70%, vermelho 90%):
 * - origem: Diárias no 1º território, R$ 10.000 alocados e nada usado;
 * - destino: Diárias no 2º território, R$ 1.000 alocados e R$ 950
 *   comprometidos (95%, vermelho). Recebendo R$ 1.000, cai para 47,5%, verde;
 * - outra rubrica: Material gráfico no 2º território, para conferir que o
 *   destino só lista pools da rubrica da origem.
 *
 * `comprometerOrigem` tira saldo da origem entre a simulação e a confirmação,
 * que é o caso do `INSUFFICIENT_BALANCE` na confirmação. O teardown restaura a
 * fotografia do orçamento (ver `orcamentoE2E.ts`), o que também desfaz os
 * remanejamentos confirmados pelos testes, e apaga os avisos de remanejamento
 * efetivado que eles dispararam.
 *
 * Roda como `postgres`, como as demais fixtures de orçamento.
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const MARCADOR = "REMANEJAMENTO_402_FIXTURE";

export type PoolDaFixture = { id: number; territorio: string };

export type RemanejamentoPoolsFixture = {
  origem: PoolDaFixture;
  destino: PoolDaFixture;
  outraRubrica: PoolDaFixture;
};

export type AlocadoDosPools = { origem: string; destino: string };

const COMUM = `${ORCAMENTO_E2E_PY}
import json
from apps.core.models import Territory
from apps.core.models.notifications import Notification
from apps.sgp.budget.models import BudgetPool, BudgetRubrica

FOTO = "remanejamento-402"
AVISOS = "/tmp/e2e-remanejamento-402-avisos"
diarias = BudgetRubrica.objects.get(slug="diarias")
grafico = BudgetRubrica.objects.get(slug="material-grafico")
t1, t2 = Territory.objects.order_by("pk")[:2]
`;

const SETUP_SCRIPT = `${COMUM}
fotografar(FOTO)
with open(AVISOS, "w") as f:
    f.write(str(Notification.objects.order_by("-pk").values_list("pk", flat=True).first() or 0))
origem = definir_pool(diarias, "territorial", "10000.00", territorio_id=t1.pk)
destino = definir_pool(diarias, "territorial", "1000.00", territorio_id=t2.pk, comprometido="950.00")
outra = definir_pool(grafico, "territorial", "3000.00", territorio_id=t2.pk)
print("${MARCADOR}_SETUP " + json.dumps({
    "origem": {"id": origem.pk, "territorio": t1.nome},
    "destino": {"id": destino.pk, "territorio": t2.nome},
    "outraRubrica": {"id": outra.pk, "territorio": t2.nome},
}))
`;

function djangoShellComoDono(script: string): string {
  return execFileSync(
    "docker",
    [
      "compose",
      "exec",
      "-T",
      "backend",
      "sh",
      "-c",
      'DB_USER=$POSTGRES_USER DB_PASSWORD=$POSTGRES_PASSWORD python manage.py shell -c "$1"',
      "sh",
      script,
    ],
    { cwd: REPO_ROOT, encoding: "utf8", timeout: 180_000 },
  );
}

function linhaDoMarcador(saida: string, etapa: string): string {
  const prefixo = `${MARCADOR}_${etapa} `;
  const linha = saida
    .split("\n")
    .map((l) => l.trim())
    .find((l) => l.startsWith(prefixo));
  if (!linha) throw new Error(`Fixture da #402 não confirmou ${etapa}:\n${saida}`);
  return linha.slice(prefixo.length);
}

export function criarRemanejamentoPoolsFixture(): RemanejamentoPoolsFixture {
  return JSON.parse(linhaDoMarcador(djangoShellComoDono(SETUP_SCRIPT), "SETUP"));
}

/** Compromete parte da origem, deixando `saldo` disponível para remanejar. */
export function comprometerOrigem(fx: RemanejamentoPoolsFixture, saldo: string): void {
  linhaDoMarcador(
    djangoShellComoDono(`${COMUM}
from decimal import Decimal
pool = BudgetPool.objects.get(pk=${fx.origem.id})
BudgetPool.objects.filter(pk=pool.pk).update(valor_comprometido=pool.valor_alocado - Decimal("${saldo}"))
print("${MARCADOR}_COMPROMETIDO ok")
`),
    "COMPROMETIDO",
  );
}

/** Devolve a origem e o destino ao estado do setup. */
export function reiniciarPools(): void {
  linhaDoMarcador(
    djangoShellComoDono(`${COMUM}
definir_pool(diarias, "territorial", "10000.00", territorio_id=t1.pk)
definir_pool(diarias, "territorial", "1000.00", territorio_id=t2.pk, comprometido="950.00")
print("${MARCADOR}_REINICIADO ok")
`),
    "REINICIADO",
  );
}

export function lerAlocado(fx: RemanejamentoPoolsFixture): AlocadoDosPools {
  return JSON.parse(
    linhaDoMarcador(
      djangoShellComoDono(`${COMUM}
alocado = dict(BudgetPool.objects.filter(pk__in=[${fx.origem.id}, ${fx.destino.id}]).values_list("pk", "valor_alocado"))
print("${MARCADOR}_ALOCADO " + json.dumps({
    "origem": f"{alocado[${fx.origem.id}]:.2f}",
    "destino": f"{alocado[${fx.destino.id}]:.2f}",
}))
`),
      "ALOCADO",
    ),
  );
}

export function removerRemanejamentoPoolsFixture(): void {
  linhaDoMarcador(
    djangoShellComoDono(`${COMUM}
restaurar(FOTO)
# Os avisos de remanejamento efetivado que os testes dispararam.
if _os.path.exists(AVISOS):
    with open(AVISOS) as f:
        Notification.objects.filter(pk__gt=int(f.read()), evento="remanejamento_efetivado").delete()
    _os.remove(AVISOS)
print("${MARCADOR}_TEARDOWN ok")
`),
    "TEARDOWN",
  );
}
