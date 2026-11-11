import { execFileSync } from "node:child_process";
import path from "node:path";

/**
 * Fixture dos alertas orçamentários e dos parâmetros globais (#403).
 *
 * - Três alertas abertos com alvo sintético (`referencia_id` a partir de
 *   990403001, escopo Meta), para não disputar a restrição de "um alerta aberto
 *   por alvo e tipo" com os alertas reais: um de semáforo em vermelho, um de
 *   subexecução e um de remanejamento excessivo, em rubricas diferentes.
 * - Os valores dos parâmetros `budget_*` que a spec altera são lidos no setup e
 *   devolvidos no teardown.
 *
 * A UGP e o Super Admin leem todos os alertas (`alertas_visiveis`), então os
 * sintéticos aparecem para eles sem depender de pool ou limite do seed.
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const MARCADOR = "ALERTAS_403_FIXTURE";
const BASE = 990403000;

type AlertaRef = { id: number; rubrica: string };

export type AlertasOrcamentoFixture = {
  vermelho: AlertaRef;
  subexecucao: AlertaRef;
  remanejamento: AlertaRef;
  /** Valores dos parâmetros antes do teste, por chave. */
  parametros: Record<string, string>;
};

const CHAVES = ["budget_subexec_min_pct"];

const COMUM = `
from apps.sgp.budget.models import BudgetAlert

def limpar():
    BudgetAlert.objects.filter(referencia_id__gt=${BASE}, referencia_id__lt=${BASE + 1000}).delete()
`;

const SETUP_SCRIPT = `${COMUM}
import json
from decimal import Decimal
from apps.core.models import SystemConfig
from apps.sgp.budget.models import BudgetRubrica

limpar()
rubricas = list(BudgetRubrica.objects.filter(ativo=True).order_by("ordem", "pk")[:3])

def alerta(n, tipo, faixa, pct, rubrica):
    a = BudgetAlert.objects.create(
        tipo=tipo, escopo="meta", referencia_id=${BASE} + n, rubrica=rubrica,
        faixa=faixa, percentual_atingido=Decimal(pct),
    )
    return {"id": a.pk, "rubrica": rubrica.nome}

print("${MARCADOR}_SETUP " + json.dumps({
    "vermelho": alerta(1, "semaforo", "vermelho", "96.50", rubricas[0]),
    "subexecucao": alerta(2, "subexecucao", "subexecucao", "41.00", rubricas[1]),
    "remanejamento": alerta(3, "remanejamento_excessivo", "", "31.00", rubricas[2]),
    "parametros": {c.chave: c.valor for c in SystemConfig.objects.filter(chave__in=${JSON.stringify(CHAVES)})},
}))
`;

function teardownScript(parametros: Record<string, string>): string {
  return `${COMUM}
import json
from apps.core.models import SystemConfig

limpar()
for chave, valor in json.loads(${JSON.stringify(JSON.stringify(parametros))}).items():
    SystemConfig.objects.filter(chave=chave).update(valor=valor)
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
