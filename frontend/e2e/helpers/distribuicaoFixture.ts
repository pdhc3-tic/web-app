import { execFileSync } from "node:child_process";
import path from "node:path";
import { ORCAMENTO_E2E_PY } from "./orcamentoE2E";

/**
 * Fixture da distribuição orçamentária (§5.3.2), sobre o orçamento por pool
 * (#398). Esta suíte GRAVA: a UGP cria e ajusta pools estaduais pela tela.
 *
 * Cada `criarDistribuicaoFixture` (um por teste) restaura a fotografia anterior
 * e monta de novo, na rubrica Material Gráfico:
 * - o pool nacional com R$ 100.000 aprovados, nada comprometido;
 * - o pool estadual de PB com R$ 10.000, R$ 8.000 comprometidos — o "já
 *   distribuído" de partida e o piso do teste do erro do servidor;
 * - nenhum pool estadual de PE, o destino livre.
 *
 * O teardown restaura a fotografia (`orcamentoE2E.ts`), apagando os pools e o
 * ledger que a tela gravou. Roda como `postgres`.
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");

export const RUBRICA = { slug: "material-grafico", nome: "Material Gráfico" };

export const APROVADO_NACIONAL = 100000;

/** Destino sem pool. No seed de demonstração, `State.nome` é a própria sigla. */
export const ESTADO_LIVRE = { sigla: "PE", nome: "PE" };

/** Destino já distribuído, com comprometido — o piso do teste do erro. */
export const ESTADO_COM_COMPROMETIDO = { sigla: "PB", nome: "PB", alocado: 10000, comprometido: 8000 };

const MARCADOR = "PDHC_E2E_DISTRIBUICAO";
const FOTO = "distribuicao";

const PRELUDIO = `${ORCAMENTO_E2E_PY}
from decimal import Decimal
from apps.core.models import State
from apps.sgp.budget.models import BudgetPool, BudgetRubrica

rubrica = BudgetRubrica.objects.get(slug="${RUBRICA.slug}")
`;

const SETUP_SCRIPT = `${PRELUDIO}
fotografar("${FOTO}")
# Os estaduais da rubrica que não são da fixture saem do recorte: o "já
# distribuído" de partida precisa ser só o de PB.
outros = BudgetPool.objects.filter(rubrica=rubrica, nivel="estadual").exclude(estado__sigla="${ESTADO_COM_COMPROMETIDO.sigla}")
outros.update(valor_alocado=Decimal("0"), valor_comprometido=Decimal("0"), valor_executado=Decimal("0"))
definir_pool(rubrica, "nacional", "${APROVADO_NACIONAL}.00")
definir_pool(
    rubrica, "estadual", "${ESTADO_COM_COMPROMETIDO.alocado}.00",
    estado=State.objects.get(sigla="${ESTADO_COM_COMPROMETIDO.sigla}"),
    comprometido="${ESTADO_COM_COMPROMETIDO.comprometido}.00",
)
print("${MARCADOR}_SETUP_OK")
`;

const TEARDOWN_SCRIPT = `${PRELUDIO}
restaurar("${FOTO}")
print("${MARCADOR}_TEARDOWN_OK")
`;

/** Como `postgres`: a restauração desliga o trigger do ledger na sessão. */
function djangoShell(script: string): string {
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
    { cwd: REPO_ROOT, encoding: "utf8", timeout: 120_000 },
  );
}

/** Restaura o que o teste anterior gravou e monta o cenário de novo. */
export function criarDistribuicaoFixture(): void {
  const saida = djangoShell(SETUP_SCRIPT);
  if (!saida.includes(`${MARCADOR}_SETUP_OK`)) {
    throw new Error(`Falha ao montar a fixture de distribuição:\n${saida}`);
  }
}

export function removerDistribuicaoFixture(): void {
  const saida = djangoShell(TEARDOWN_SCRIPT);
  if (!saida.includes(`${MARCADOR}_TEARDOWN_OK`)) {
    throw new Error(`Falha ao remover a fixture de distribuição:\n${saida}`);
  }
}

/** O `valor_alocado` do pool estadual da sigla na rubrica, ou null se não existe. */
export function valorAlocadoNoBanco(sigla: string): string | null {
  const saida = djangoShell(`${PRELUDIO}
p = BudgetPool.objects.filter(rubrica=rubrica, nivel="estadual", estado__sigla="${sigla}").first()
print("${MARCADOR}_VALOR " + (str(p.valor_alocado) if p and p.valor_alocado else "NENHUMA"))
`);
  const marca = `${MARCADOR}_VALOR `;
  const linha = saida.split("\n").find((l) => l.startsWith(marca));
  if (!linha) throw new Error(`Falha ao ler o pool:\n${saida}`);
  const valor = linha.slice(marca.length).trim();
  return valor === "NENHUMA" ? null : valor;
}

/** Compromete parte do pool nacional, para a barra mostrar a parcela consumida. */
export function comprometerNacional(valor: number): void {
  const saida = djangoShell(`${PRELUDIO}
atualizados = BudgetPool.objects.filter(rubrica=rubrica, nivel="nacional").update(valor_comprometido=Decimal("${valor}.00"))
if not atualizados:
    raise RuntimeError("Pool nacional da fixture nao encontrado")
print("${MARCADOR}_COMPROMETIDO_OK")
`);
  if (!saida.includes(`${MARCADOR}_COMPROMETIDO_OK`)) {
    throw new Error(`Falha ao comprometer o nacional:\n${saida}`);
  }
}
