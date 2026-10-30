import { execFileSync } from "node:child_process";
import path from "node:path";

/**
 * Fixture do ciclo de vida completo da demanda (Issue #317).
 *
 * Diferente das fixtures das #295 e #296, ela NÃO cria demanda nenhuma: as
 * jornadas criam, montam, submetem e decidem tudo pela tela. Aqui só fica o
 * que o `seed_demo` não entrega pronto para isso:
 *
 * - uma atividade agendada por jornada, no Território RN do ADT Ewerton;
 * - uma atividade com uma demanda em Rascunho, só para consultar o saldo na
 *   montagem (a jornada do cancelamento compara o antes e o depois);
 * - a verba territorial de alimentação, de R$ 10.317,00 (valor-marcador da
 *   limpeza). O seed já tem uma de R$ 60.000 em RN, mas na meta 8: as
 *   atividades daqui ficam numa ação de OUTRA meta, para as jornadas não
 *   mexerem no saldo do seed — o motor procura a verba por meta, rubrica e
 *   território.
 *
 * O limite individual de alimentação do Ewerton começa em R$ 5.000 sem nada
 * comprometido nem executado, e volta à foto tirada no setup no teardown.
 *
 * O setup também limpa o que uma execução interrompida tenha deixado: os
 * testes não dependem de estado anterior.
 *
 * Roda como `postgres` por causa da row-level security de `sgd_demand`.
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const MARCADOR = "CICLO_317_FIXTURE";

export const PREFIXO_317 = "E2E-317";

type Ref = { id: number; titulo: string };

export type CicloDemandaFixture = {
  feliz: Ref;
  devolucao: Ref;
  recusa: Ref;
  cancelamento: Ref;
  /** Demanda em Rascunho onde a jornada do cancelamento lê o saldo. */
  consultaSaldo: Ref;
  limite: { limite: string; comprometido: string; executado: string } | null;
};

const COMUM = `
from decimal import Decimal
from django.contrib.auth import get_user_model
from apps.sgp.models import Activity, BudgetIncreaseRequest
from apps.sgp.models.budget import BudgetAllocation, BudgetRubrica, BudgetTransaction
from apps.sgd.models.demand import Demand
from apps.sgd.models.approval_step import ApprovalStep
from apps.sgd.models.individual_limit import DemandIndividualLimit

P = "${PREFIXO_317}"
VERBA = Decimal("10317.00")
RUBRICA = "alimentacao-refeicoes"
U = get_user_model()
adt = U.objects.get(email="ewerton.bandeira@demo.pdhc.local")
territorio_id = adt.profiles.get(perfil__slug="adt-acr").territorio_id

def limpar():
    demandas = Demand.objects.filter(titulo__startswith=P)
    ids = [str(pk) for pk in demandas.values_list("pk", flat=True)]
    BudgetIncreaseRequest.objects.filter(demanda_id__in=ids).delete()
    ApprovalStep.objects.filter(demanda__in=demandas).delete()
    verbas = BudgetAllocation.objects.filter(nivel="territorial", territorio_id=territorio_id, valor_alocado=VERBA)
    BudgetTransaction.objects.filter(allocation__in=verbas).delete()
    demandas.delete()
    Activity.objects.filter(titulo__startswith=P).delete()
    verbas.delete()
`;

const SETUP_SCRIPT = `${COMUM}
import json
from datetime import timedelta
from django.utils import timezone
from apps.core.models import Municipality
from apps.sgp.models.workplan import WorkPlanAcao
from apps.sgd.services import demand as ds

limpar()
rubrica = BudgetRubrica.objects.get(slug=RUBRICA)

# Uma ação de meta sem verba de alimentação neste território: a verba da
# fixture não colide com a do seed (única por meta, rubrica e território).
metas_com_verba = BudgetAllocation.objects.filter(
    nivel="territorial", territorio_id=territorio_id, rubrica=rubrica,
).values_list("meta_id", flat=True)
acao = WorkPlanAcao.objects.exclude(meta_id__in=list(metas_com_verba)).order_by("meta_id", "pk").first()
if acao is None:
    raise RuntimeError("Nenhuma ação fora das metas com verba de alimentação: rode manage.py seed_demo --reset")
BudgetAllocation.objects.create(
    meta_id=acao.meta_id, rubrica=rubrica, nivel="territorial", territorio_id=territorio_id, valor_alocado=VERBA,
)

limite = DemandIndividualLimit.objects.filter(solicitante=adt, rubrica=rubrica).first()
foto = limite and {
    "limite": str(limite.valor_limite),
    "comprometido": str(limite.valor_comprometido),
    "executado": str(limite.valor_executado),
}
if limite is None:
    limite = DemandIndividualLimit(solicitante=adt, rubrica=rubrica)
limite.valor_limite = Decimal("5000")
limite.valor_comprometido = Decimal("0")
limite.valor_executado = Decimal("0")
limite.save()

municipio = Municipality.objects.filter(territory_id=territorio_id).order_by("nome").first()
quando = timezone.now() + timedelta(days=20)

def atividade(titulo):
    a = Activity.objects.create(
        titulo=f"{P} {titulo}", tipo_atividade="intercambio", acao=acao, municipio=municipio,
        forma_atuacao="realizacao", ambito="territorial", tecnico_responsavel=adt,
        data_inicio=quando, data_fim=quando, status="agendado", criado_por=adt,
        descricao_narrativa="Criada pela fixture E2E da issue 317.",
    )
    return {"id": a.pk, "titulo": a.titulo}

saldo = atividade("Reunião do colegiado territorial")
consulta = ds.criar_demanda(
    titulo=f"{P} Consulta de saldo", activity=Activity.objects.get(pk=saldo["id"]), justificativa="", solicitante=adt,
)

print("${MARCADOR}_SETUP " + json.dumps({
    "feliz": atividade("Feira agroecológica do território"),
    "devolucao": atividade("Oficina de beneficiamento de frutas"),
    "recusa": atividade("Encontro de mulheres rurais"),
    "cancelamento": atividade("Dia de campo em quintais produtivos"),
    "consultaSaldo": {"id": consulta.pk, "titulo": consulta.titulo},
    "limite": foto,
}))
`;

function teardownScript(foto: CicloDemandaFixture["limite"]): string {
  return `${COMUM}
import json
limpar()
foto = json.loads(${JSON.stringify(JSON.stringify(foto))})
limite = DemandIndividualLimit.objects.filter(solicitante=adt, rubrica__slug=RUBRICA).first()
if limite is not None:
    if foto is None:
        limite.delete()
    else:
        limite.valor_limite = Decimal(foto["limite"])
        limite.valor_comprometido = Decimal(foto["comprometido"])
        limite.valor_executado = Decimal(foto["executado"])
        limite.save(update_fields=["valor_limite", "valor_comprometido", "valor_executado"])
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

export function criarCicloDemandaFixture(): CicloDemandaFixture {
  const saida = djangoShellComoDono(SETUP_SCRIPT);
  const linha = saida
    .split("\n")
    .map((l) => l.trim())
    .find((l) => l.startsWith(`${MARCADOR}_SETUP `));
  if (!linha) throw new Error(`Fixture da #317 não confirmou o setup:\n${saida}`);
  return JSON.parse(linha.slice(`${MARCADOR}_SETUP `.length)) as CicloDemandaFixture;
}

export function removerCicloDemandaFixture(fx: CicloDemandaFixture): void {
  const saida = djangoShellComoDono(teardownScript(fx.limite));
  if (!saida.includes(`${MARCADOR}_TEARDOWN_OK`)) {
    throw new Error(`Fixture da #317 não confirmou o teardown:\n${saida}`);
  }
}
