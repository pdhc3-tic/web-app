import { execFileSync } from "node:child_process";
import path from "node:path";
import { ORCAMENTO_E2E_PY } from "./orcamentoE2E";

/**
 * Fixture dos alertas orçamentários e dos parâmetros globais (#403).
 *
 * Os alertas são de pool, como os que o backend gera, e saem dos services de
 * `apps/sgp/budget/alertas.py`:
 * - semáforo vermelho: um pool territorial de Diárias com 96,5% comprometido,
 *   aberto por `sincronizar_semaforo` (o mesmo cálculo da tarefa periódica);
 * - subexecução e remanejamento excessivo: no pool nacional de Material
 *   gráfico e no de Locação de veículo, que é onde o backend avalia os
 *   alertas por rubrica, abertos por `_abrir_ou_resolver`.
 *
 * Nenhum aviso é enviado: a fixture abre os alertas sem passar pela
 * notificação. O orçamento é fotografado antes e restaurado no teardown
 * (`orcamentoE2E.ts`), o que também apaga os alertas criados depois da foto.
 *
 * Os seis parâmetros `budget_*` são lidos no setup, como estão gravados, e o
 * que a spec alterar volta no teardown pelo `save()`, que limpa o cache do
 * `get_config`.
 *
 * Roda como `postgres`, como as demais fixtures de orçamento.
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const MARCADOR = "ALERTAS_403_FIXTURE";

type AlertaRef = { id: number; rubrica: string };

export type AlertasOrcamentoFixture = {
  vermelho: AlertaRef;
  subexecucao: AlertaRef;
  remanejamento: AlertaRef;
  /** Valores gravados dos parâmetros antes do teste, por chave. */
  parametros: Record<string, string>;
};

/** Lidas no setup para a spec conferir a tela; no teardown, volta só o que mudou. */
const CHAVES = [
  "budget_limit_period",
  "budget_limit_carry_over",
  "budget_overallocation_allowed",
  "budget_subexec_alert_months",
  "budget_subexec_min_pct",
  "budget_transfer_alert_pct",
];

const COMUM = `${ORCAMENTO_E2E_PY}
import json
from apps.core.models import SystemConfig

FOTO = "alertas-403"
`;

const SETUP_SCRIPT = `${COMUM}
from decimal import Decimal
from apps.core.models import Territory
from apps.sgp.budget import alertas as A
from apps.sgp.budget.models import BudgetAlert, BudgetRubrica
from apps.sgp.budget.rls import visao_total

fotografar(FOTO)
territorio = Territory.objects.order_by("pk").first()
diarias = BudgetRubrica.objects.get(slug="diarias")
grafico = BudgetRubrica.objects.get(slug="material-grafico")
veiculo = BudgetRubrica.objects.get(slug="locacao-veiculo")

with visao_total():
    territorial = definir_pool(diarias, "territorial", "1000.00", territorio_id=territorio.pk, comprometido="965.00")
    A.sincronizar_semaforo(territorial)
    vermelho = BudgetAlert.objects.get(
        escopo="pool", referencia_id=territorial.pk, tipo="semaforo", resolvido_em__isnull=True,
    )
    nacional_grafico = definir_pool(grafico, "nacional", "50000.00", executado="20500.00")
    subexecucao = A._abrir_ou_resolver(
        nacional_grafico, "subexecucao", faixa="subexecucao", percentual=Decimal("41.00"), abrir=True,
    ) or BudgetAlert.objects.get(escopo="pool", referencia_id=nacional_grafico.pk, tipo="subexecucao", resolvido_em__isnull=True)
    nacional_veiculo = definir_pool(veiculo, "nacional", "80000.00")
    remanejamento = A._abrir_ou_resolver(
        nacional_veiculo, "remanejamento_excessivo", faixa="", percentual=Decimal("31.00"), abrir=True,
    ) or BudgetAlert.objects.get(escopo="pool", referencia_id=nacional_veiculo.pk, tipo="remanejamento_excessivo", resolvido_em__isnull=True)

print("${MARCADOR}_SETUP " + json.dumps({
    "vermelho": {"id": vermelho.pk, "rubrica": diarias.nome},
    "subexecucao": {"id": subexecucao.pk, "rubrica": grafico.nome},
    "remanejamento": {"id": remanejamento.pk, "rubrica": veiculo.nome},
    "parametros": {c.chave: c.valor for c in SystemConfig.objects.filter(chave__in=${JSON.stringify(CHAVES)})},
}))
`;

function teardownScript(parametros: Record<string, string>): string {
  return `${COMUM}
restaurar(FOTO)
for chave, valor in json.loads(${JSON.stringify(JSON.stringify(parametros))}).items():
    config = SystemConfig.objects.filter(chave=chave).first()
    if config is not None and config.valor != valor:
        config.valor = valor
        config.save()
print("${MARCADOR}_TEARDOWN_OK")
`;
}

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

export function criarAlertasOrcamentoFixture(): AlertasOrcamentoFixture {
  const saida = djangoShellComoDono(SETUP_SCRIPT);
  const linha = saida
    .split("\n")
    .map((l) => l.trim())
    .find((l) => l.startsWith(`${MARCADOR}_SETUP `));
  if (!linha) throw new Error(`Fixture da #403 não confirmou o setup:\n${saida}`);
  return JSON.parse(linha.slice(`${MARCADOR}_SETUP `.length)) as AlertasOrcamentoFixture;
}

export function removerAlertasOrcamentoFixture(parametros: Record<string, string> = {}): void {
  const saida = djangoShellComoDono(teardownScript(parametros));
  if (!saida.includes(`${MARCADOR}_TEARDOWN_OK`)) {
    throw new Error(`Fixture da #403 não confirmou o teardown:\n${saida}`);
  }
}
