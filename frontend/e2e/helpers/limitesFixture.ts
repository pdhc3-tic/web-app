import { execFileSync } from "node:child_process";
import path from "node:path";
import { ORCAMENTO_E2E_PY } from "./orcamentoE2E";

/**
 * Fixture da gestão de limites de gasto (#400), sobre o backend do #385.
 *
 * Monta, pelos serviços de `apps/sgp/budget/limites.py`:
 * - o padrão do perfil ADT/ACR em Material Gráfico (R$ 1.500), criado pela UGP;
 * - a linha herdada da ADT Marina nessa rubrica — o que a primeira reserva
 *   faria —, de modo que o padrão fica "em uso" e a alteração dele é agendada
 *   para o período seguinte;
 * - o pool territorial de Diárias do território da Marina em R$ 7.000, para a
 *   sobrealocação ter um teto conhecido.
 *
 * Os testes só alteram o que a fixture criou ou o que eles mesmos criam: o
 * `restaurar` apaga as linhas novas, mas não desfaz o encerramento de um
 * padrão antigo. A sobrealocação (`budget_overallocation_allowed`) é ligada e
 * desligada aqui, limpando o cache do `get_config`, e volta ao valor original
 * no teardown.
 *
 * Roda como `postgres`, como as demais fixtures de orçamento.
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const MARCADOR = "LIMITES_400_FIXTURE";

export type LimitesFixture = {
  marina: { id: number; nome: string };
  /** Primeiro dia do período seguinte, `YYYY-MM-DD`. */
  proximoInicio: string;
  sobrealocacaoOriginal: boolean;
};

const COMUM = `${ORCAMENTO_E2E_PY}
from django.core.cache import cache
from apps.core.models import SystemConfig

FOTO = "limites-400"
CHAVE = "budget_overallocation_allowed"

def sobrealocacao(permitida):
    SystemConfig.objects.filter(chave=CHAVE).update(valor="True" if permitida else "False")
    cache.delete(f"system_config:{CHAVE}")
`;

const SETUP_SCRIPT = `${COMUM}
import json
from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.db import transaction
from apps.core.models import Role
from apps.core.utils import get_config
from apps.sgp.budget import limites as L
from apps.sgp.budget.models import BudgetRubrica

restaurar(FOTO)
original = SystemConfig.objects.get(chave=CHAVE).valor == "True"
sobrealocacao(True)
fotografar(FOTO)

U = get_user_model()
ugp = U.objects.get(email="beatriz.nogueira@demo.pdhc.local")
marina = U.objects.get(email="marina.albuquerque@demo.pdhc.local")
grafico = BudgetRubrica.objects.get(slug="material-grafico")
diarias = BudgetRubrica.objects.get(slug="diarias")
adt = Role.objects.get(slug="adt-acr")

L.criar_padrao(perfil=adt, rubrica=grafico, valor_limite=Decimal("1500.00"), usuario=ugp,
               justificativa="Padrão da fixture E2E da issue 400.")
with transaction.atomic():
    herdada = L.travar_limite_vigente(user_id=marina.pk, rubrica_id=grafico.pk, criar=True)
assert herdada is not None and herdada.herdado, herdada

territorio = marina.profiles.get(perfil__slug="adt-acr").territorio_id
definir_pool(diarias, "territorial", "7000.00", territorio_id=territorio)

proximo = L.periodo_de(L.hoje())[1] + timedelta(days=1)
print("${MARCADOR}_SETUP " + json.dumps({
    "marina": {"id": marina.pk, "nome": marina.nome},
    "proximoInicio": proximo.isoformat(),
    "sobrealocacaoOriginal": original,
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

function confirmar(saida: string, linha: string): void {
  if (!saida.includes(linha)) throw new Error(`Fixture da #400 não confirmou ${linha}:\n${saida}`);
}

export function criarLimitesFixture(): LimitesFixture {
  const saida = djangoShellComoDono(SETUP_SCRIPT);
  const linha = saida
    .split("\n")
    .map((l) => l.trim())
    .find((l) => l.startsWith(`${MARCADOR}_SETUP `));
  if (!linha) throw new Error(`Fixture da #400 não confirmou o setup:\n${saida}`);
  return JSON.parse(linha.slice(`${MARCADOR}_SETUP `.length)) as LimitesFixture;
}

/** Liga ou desliga a sobrealocação no backend real (e limpa o cache do parâmetro). */
export function definirSobrealocacao(permitida: boolean): void {
  confirmar(
    djangoShellComoDono(`${COMUM}
sobrealocacao(${permitida ? "True" : "False"})
print("${MARCADOR}_SOBREALOCACAO")
`),
    `${MARCADOR}_SOBREALOCACAO`,
  );
}

export function removerLimitesFixture(fx?: LimitesFixture): void {
  const original = fx?.sobrealocacaoOriginal ?? true;
  confirmar(
    djangoShellComoDono(`${COMUM}
restaurar(FOTO)
sobrealocacao(${original ? "True" : "False"})
print("${MARCADOR}_TEARDOWN_OK")
`),
    `${MARCADOR}_TEARDOWN_OK`,
  );
}
