import { execFileSync } from "node:child_process";
import path from "node:path";
import { ORCAMENTO_E2E_PY } from "./orcamentoE2E";

/**
 * Fixture do histórico de remanejamentos (#466), contra o backend real.
 *
 * Monta dois pools de Diárias e dois de Material gráfico em territórios
 * diferentes e faz três remanejamentos diretos pela UGP, pelo mesmo serviço do
 * Remanejar (`remanejar_com_registro`): dois em Diárias e um em Material
 * gráfico, para o filtro por rubrica restringir de verdade. Devolve os ids e as
 * contagens que a listagem deve trazer, lidas do banco.
 *
 * O teardown restaura a fotografia do orçamento (ver `orcamentoE2E.ts`), o que
 * apaga os remanejamentos e os pools criados, e os avisos de remanejamento
 * efetivado que eles dispararam. Roda como `postgres`, como as demais fixtures
 * de orçamento.
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const MARCADOR = "HISTORICO_466_FIXTURE";

export type HistoricoRemanejamentosFixture = {
  /** Ids dos remanejamentos criados, do mais antigo ao mais recente. */
  diarias: number[];
  grafico: number;
  /** Remanejamentos na listagem, sem filtro e com `rubrica=material-grafico`. */
  total: number;
  totalGrafico: number;
};

const COMUM = `${ORCAMENTO_E2E_PY}
import json
from django.contrib.auth import get_user_model
from apps.core.models import Territory
from apps.core.models.notifications import Notification
from apps.sgp.budget import services as budget_service
from apps.sgp.budget.models import BudgetRubrica, BudgetTransfer

FOTO = "historico-466"
AVISOS = "/tmp/e2e-historico-466-avisos"
`;

const SETUP_SCRIPT = `${COMUM}
fotografar(FOTO)
with open(AVISOS, "w") as f:
    f.write(str(Notification.objects.order_by("-pk").values_list("pk", flat=True).first() or 0))

ugp = get_user_model().objects.filter(profiles__perfil__slug="ugp", ativo=True).order_by("pk").first()
diarias = BudgetRubrica.objects.get(slug="diarias")
grafico = BudgetRubrica.objects.get(slug="material-grafico")
t1, t2 = Territory.objects.order_by("pk")[:2]

d1 = definir_pool(diarias, "territorial", "10000.00", territorio_id=t1.pk)
d2 = definir_pool(diarias, "territorial", "2000.00", territorio_id=t2.pk, comprometido="500.00")
g1 = definir_pool(grafico, "territorial", "3000.00", territorio_id=t1.pk)
g2 = definir_pool(grafico, "territorial", "1000.00", territorio_id=t2.pk)

def remanejar(origem, destino, valor, motivo):
    budget_service.remanejar_com_registro(
        origem=origem, destino=destino, valor=_D(valor), usuario=ugp, justificativa=motivo,
    )
    return BudgetTransfer.objects.order_by("-pk").values_list("pk", flat=True).first()

ids = [
    remanejar(d1, d2, "1500.00", "E2E 466: reforço de diárias no segundo território."),
    remanejar(d2, d1, "250.00", "E2E 466: devolução parcial ao primeiro território."),
]
g = remanejar(g1, g2, "400.00", "E2E 466: material gráfico para as oficinas.")
print("${MARCADOR}_SETUP " + json.dumps({
    "diarias": ids,
    "grafico": g,
    "total": BudgetTransfer.objects.count(),
    "totalGrafico": BudgetTransfer.objects.filter(pool_destino__rubrica=grafico).count(),
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
  if (!linha) throw new Error(`Fixture da #466 não confirmou ${etapa}:\n${saida}`);
  return linha.slice(prefixo.length);
}

export function criarHistoricoRemanejamentosFixture(): HistoricoRemanejamentosFixture {
  return JSON.parse(linhaDoMarcador(djangoShellComoDono(SETUP_SCRIPT), "SETUP"));
}

export function removerHistoricoRemanejamentosFixture(): void {
  linhaDoMarcador(
    djangoShellComoDono(`${COMUM}
restaurar(FOTO)
if _os.path.exists(AVISOS):
    with open(AVISOS) as f:
        Notification.objects.filter(pk__gt=int(f.read()), evento="remanejamento_efetivado").delete()
    _os.remove(AVISOS)
print("${MARCADOR}_TEARDOWN ok")
`),
    "TEARDOWN",
  );
}
