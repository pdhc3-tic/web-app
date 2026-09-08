import { execFileSync } from "node:child_process";
import path from "node:path";

/**
 * Fixture da tela de distribuição orçamentária (§5.3.2).
 *
 * ─── Por que uma Meta só dela ───────────────────────────────────────────────
 *
 * Esta suíte ESCREVE no orçamento, e o que ela grava passa pelo service — logo
 * nasce com `BudgetTransaction`. A de `orcamento.spec.ts` usa as Metas 1 e 2 e
 * apaga por Meta no teardown; se as duas dividissem Meta, uma limparia o
 * cenário da outra no meio da execução. A Meta 7 é exclusiva daqui.
 *
 * ─── Por que o teardown apaga as transactions primeiro ──────────────────────
 *
 * `BudgetTransaction.delete()` levanta ProtectedError e `allocation` é PROTECT:
 * uma alocação criada pela tela não sai por nenhum caminho de instância. O que
 * funciona é `QuerySet.delete()`, que é DELETE em massa e não chama o método do
 * model — apagando primeiro as transactions, some o que protegia a alocação.
 *
 * Sem isso cada execução deixaria lixo permanente no banco de demonstração, e a
 * segunda rodada encontraria "Ajustar" onde esperava "Distribuir".
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");

/** Meta reservada a esta suíte. */
export const META_DISTRIBUICAO = 7;

/** Rubrica em que o cenário é montado. */
export const RUBRICA = { slug: "material-grafico", nome: "Material Gráfico" };

/** Teto nacional: é contra este saldo que a tela valida. */
export const APROVADO_NACIONAL = 100000;

/** Estado livre — o teste de criação distribui para ele. */
export const ESTADO_LIVRE = { sigla: "PE", nome: "PE" };

/**
 * Estado que já tem alocação COM valor comprometido.
 *
 * O comprometido é o que torna possível o teste do erro ancorado: reduzir
 * abaixo dele é recusado por `atualizar_valor_alocado` com a mensagem em
 * `valor_alocado`, e a tela não tem como antecipar isso — ela só valida teto.
 */
export const ESTADO_COM_COMPROMETIDO = {
  sigla: "PB",
  nome: "PB",
  alocado: 10000,
  comprometido: 8000,
};

const MARCADOR = "PDHC_E2E_DISTRIBUICAO";

/**
 * Estado inicial: o pai nacional e uma estadual com comprometido.
 *
 * Ambos criados pelo ORM cru, sem transaction — o cenário de partida precisa
 * sair limpo no teardown, e só o que a TELA gravar é que terá transaction.
 */
const SETUP_SCRIPT = `
from decimal import Decimal

from apps.core.models import State
from apps.sgp.models import BudgetAllocation, BudgetTransaction, BudgetRubrica, WorkPlanMeta

meta = WorkPlanMeta.objects.get(numero=${META_DISTRIBUICAO})
rubrica = BudgetRubrica.objects.get(slug="${RUBRICA.slug}")

# Zera tudo da Meta antes de montar: uma execucao anterior interrompida pode ter
# deixado alocacoes com transaction, e elas so saem nesta ordem.
alocacoes = BudgetAllocation.objects.filter(meta=meta)
BudgetTransaction.objects.filter(allocation__in=alocacoes).delete()
alocacoes.delete()

BudgetAllocation.objects.create(
    meta=meta, rubrica=rubrica, nivel="nacional",
    valor_alocado=Decimal("${APROVADO_NACIONAL}.00"),
    valor_comprometido=Decimal("0.00"), valor_executado=Decimal("0.00"),
)

BudgetAllocation.objects.create(
    meta=meta, rubrica=rubrica, nivel="estadual",
    estado=State.objects.get(sigla="${ESTADO_COM_COMPROMETIDO.sigla}"),
    valor_alocado=Decimal("${ESTADO_COM_COMPROMETIDO.alocado}.00"),
    valor_comprometido=Decimal("${ESTADO_COM_COMPROMETIDO.comprometido}.00"),
    valor_executado=Decimal("0.00"),
)

print("${MARCADOR}_SETUP_OK " + str(meta.pk))
`;

const TEARDOWN_SCRIPT = `
from apps.sgp.models import BudgetAllocation, BudgetTransaction, WorkPlanMeta

meta = WorkPlanMeta.objects.filter(numero=${META_DISTRIBUICAO}).first()
if meta is not None:
    alocacoes = BudgetAllocation.objects.filter(meta=meta)
    BudgetTransaction.objects.filter(allocation__in=alocacoes).delete()
    alocacoes.delete()

print("${MARCADOR}_TEARDOWN_OK")
`;

function djangoShell(script: string): string {
  return execFileSync(
    "docker",
    ["compose", "exec", "-T", "backend", "python", "manage.py", "shell", "-c", script],
    { cwd: REPO_ROOT, encoding: "utf8", timeout: 120_000 },
  );
}

/** Monta o cenário e devolve a PK da Meta (a URL e os selects usam id, não número). */
export function criarDistribuicaoFixture(): number {
  const saida = djangoShell(SETUP_SCRIPT);
  const marca = `${MARCADOR}_SETUP_OK `;
  const linha = saida.split("\n").find((l) => l.startsWith(marca));
  if (!linha) {
    throw new Error(`Falha ao montar a fixture de distribuição:\n${saida}`);
  }
  return Number(linha.slice(marca.length).trim());
}

export function removerDistribuicaoFixture(): void {
  const saida = djangoShell(TEARDOWN_SCRIPT);
  if (!saida.includes(`${MARCADOR}_TEARDOWN_OK`)) {
    throw new Error(`Falha ao remover a fixture de distribuição:\n${saida}`);
  }
}

/**
 * Lê do banco o `valor_alocado` gravado para um estado — a única forma de
 * provar o que a máscara realmente enviou, já que a tela reexibe o valor
 * formatado e um `toContainText` não distinguiria "1.234,56" de "123.456".
 */
export function valorAlocadoNoBanco(sigla: string): string | null {
  const saida = djangoShell(`
from apps.sgp.models import BudgetAllocation, WorkPlanMeta

meta = WorkPlanMeta.objects.get(numero=${META_DISTRIBUICAO})
a = BudgetAllocation.objects.filter(
    meta=meta, nivel="estadual", estado__sigla="${sigla}",
).first()
print("${MARCADOR}_VALOR " + (str(a.valor_alocado) if a else "NENHUMA"))
`);
  const marca = `${MARCADOR}_VALOR `;
  const linha = saida.split("\n").find((l) => l.startsWith(marca));
  if (!linha) throw new Error(`Falha ao ler a alocação:\n${saida}`);
  const valor = linha.slice(marca.length).trim();
  return valor === "NENHUMA" ? null : valor;
}
