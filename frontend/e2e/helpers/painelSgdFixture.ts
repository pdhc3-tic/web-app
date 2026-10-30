import { execFileSync } from "node:child_process";
import path from "node:path";

/**
 * Fixture da home do SGD (Issue #318), para o Articulador de RN (`articuladorPB`).
 *
 * Três demandas Submetidas numa atividade de RN, gravadas direto no status e
 * com `status_alterado_em` controlado, para provar a ordem da fila (tempo de
 * espera, depois valor):
 * - `antiga`: há 12 dias, R$ 500 — primeira, e também parada há 5+ dias úteis;
 * - `maior` e `menor`: há 2 dias, no mesmo dia; a `menor` (R$ 300) entrou de
 *   manhã e a `maior` (R$ 900) à tarde — mesmo dia de espera, então o maior
 *   valor vem antes, ainda que tenha chegado depois.
 *
 * E duas verbas ESTADUAIS de RN (valor-marcador R$ 10.318,00) com o
 * comprometido materializado: Alimentação a 95% (vermelho) e Material
 * Gráfico a ~73% (amarelo). O seed não tem verba estadual nenhuma.
 *
 * Roda como `postgres` por causa da row-level security de `sgd_demand`.
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const MARCADOR = "PAINEL_SGD_318_FIXTURE";

export const PREFIXO_318 = "E2E-318";

type Ref = { id: number; titulo: string };

export type PainelSgdFixture = {
  antiga: Ref;
  maior: Ref;
  menor: Ref;
  metaId: number;
};

const COMUM = `
from decimal import Decimal
from django.contrib.auth import get_user_model
from apps.sgp.models import Activity
from apps.sgp.models.budget import BudgetAllocation
from apps.sgd.models.demand import Demand

P = "${PREFIXO_318}"
VERBA = Decimal("10318.00")
U = get_user_model()
adt = U.objects.get(email="ewerton.bandeira@demo.pdhc.local")
territorio_id = adt.profiles.get(perfil__slug="adt-acr").territorio_id

def limpar():
    Demand.objects.filter(titulo__startswith=P).delete()
    Activity.objects.filter(titulo__startswith=P).delete()
    BudgetAllocation.objects.filter(nivel="estadual", valor_alocado=VERBA).delete()
`;

const SETUP_SCRIPT = `${COMUM}
import json
from datetime import timedelta
from django.utils import timezone
from apps.core.models import Municipality, State
from apps.sgp.models.budget import BudgetRubrica
from apps.sgp.models.workplan import WorkPlanAcao
from apps.sgd.models.demand_request import DemandRequest

limpar()
acao = WorkPlanAcao.objects.order_by("pk").first()
municipio = Municipality.objects.filter(territory_id=territorio_id).order_by("nome").first()
quando = timezone.now() + timedelta(days=20)
atividade = Activity.objects.create(
    titulo=f"{P} Feira estadual da agricultura familiar", tipo_atividade="intercambio", acao=acao,
    municipio=municipio, forma_atuacao="realizacao", ambito="territorial", tecnico_responsavel=adt,
    data_inicio=quando, data_fim=quando, status="agendado", criado_por=adt,
    descricao_narrativa="Criada pela fixture E2E da issue 318.",
)
alimentacao = BudgetRubrica.objects.get(slug="alimentacao-refeicoes")
hoje = timezone.localtime()

def submetida(titulo, valor, dias, hora):
    d = Demand.objects.create(titulo=f"{P} {titulo}", activity=atividade, justificativa="", solicitante=adt, status="submetida")
    DemandRequest.objects.create(demanda=d, tipo="alimentacao", rubrica=alimentacao, campos_json={}, valor_estimado=Decimal(valor))
    quando = (hoje - timedelta(days=dias)).replace(hour=hora, minute=0, second=0, microsecond=0)
    Demand.objects.filter(pk=d.pk).update(status_alterado_em=quando)
    return {"id": d.pk, "titulo": d.titulo}

antiga = submetida("Almoço do encontro estadual", "500", 12, 10)
menor = submetida("Lanche da reunião de coordenação", "300", 2, 9)
maior = submetida("Refeições da caravana", "900", 2, 15)

rn = State.objects.get(sigla="RN")
for slug, comprometido in (("alimentacao-refeicoes", "9802.10"), ("material-grafico", "7500.00")):
    BudgetAllocation.objects.create(
        meta_id=acao.meta_id, rubrica=BudgetRubrica.objects.get(slug=slug), nivel="estadual", estado=rn,
        valor_alocado=VERBA, valor_comprometido=Decimal(comprometido),
    )

print("${MARCADOR}_SETUP " + json.dumps({"antiga": antiga, "maior": maior, "menor": menor, "metaId": acao.meta_id}))
`;

const TEARDOWN_SCRIPT = `${COMUM}
limpar()
print("${MARCADOR}_TEARDOWN_OK")
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

export function criarPainelSgdFixture(): PainelSgdFixture {
  const saida = djangoShellComoDono(SETUP_SCRIPT);
  const linha = saida
    .split("\n")
    .map((l) => l.trim())
    .find((l) => l.startsWith(`${MARCADOR}_SETUP `));
  if (!linha) throw new Error(`Fixture da #318 não confirmou o setup:\n${saida}`);
  return JSON.parse(linha.slice(`${MARCADOR}_SETUP `.length)) as PainelSgdFixture;
}

export function removerPainelSgdFixture(): void {
  const saida = djangoShellComoDono(TEARDOWN_SCRIPT);
  if (!saida.includes(`${MARCADOR}_TEARDOWN_OK`)) {
    throw new Error(`Fixture da #318 não confirmou o teardown:\n${saida}`);
  }
}
