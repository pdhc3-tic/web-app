import { execFileSync } from "node:child_process";
import path from "node:path";

/**
 * Fixture do painel de demandas (Issue #296).
 *
 * O `seed_demo` não tem demanda, limite individual nem alocação territorial
 * para o Território RN. A fixture monta tudo pelos PRÓPRIOS services do SGD —
 * criar, adicionar solicitação, submeter (que reserva as duas travas) e
 * pré-autorizar —, para as demandas chegarem a cada status como chegariam
 * pela tela, com reservas de saldo de verdade:
 *
 * - `preAutorizar` e `devolver`: Submetidas (fila do Articulador de RN);
 * - `autorizar` e `recusar`: Pré-autorizadas (fila da UGP);
 * - `atender`: Autorizada (fila da FGD).
 *
 * Solicitante: o ADT do Território RN. Articulador de RN: o `articuladorPB`
 * (PB/RN/BA/MG); o `articuladorPE` não atua em RN e não deve vê-las.
 *
 * Limite individual de R$ 10.000 e pool territorial de R$ 20.296: com 5
 * demandas de R$ 1.200 reservadas (60%), ajustar a de `autorizar` para
 * R$ 3.000 leva o limite individual de verde para amarelo — o caso do
 * preview com mudança de faixa.
 *
 * Roda como `postgres` por causa da row-level security de `sgd_demand`.
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const MARCADOR = "PAINEL_DEMANDAS_FIXTURE";

export const PREFIXO_296 = "E2E-296";

type Ref = { id: number; titulo: string };

export type PainelDemandasFixture = {
  preAutorizar: Ref;
  devolver: Ref;
  autorizar: Ref & { solicitacaoId: number };
  recusar: Ref;
  atender: Ref;
};

const COMUM = `
from decimal import Decimal
from django.contrib.auth import get_user_model
from apps.sgp.models import Activity
from apps.sgp.models.budget import BudgetAllocation, BudgetRubrica, BudgetTransaction
from apps.sgd.models.demand import Demand
from apps.sgd.models.approval_step import ApprovalStep
from apps.sgd.models.individual_limit import DemandIndividualLimit

P = "${PREFIXO_296}"
POOL = Decimal("20296.00")
U = get_user_model()
adt = U.objects.get(email="ewerton.bandeira@demo.pdhc.local")
territorio_id = adt.profiles.get(perfil__slug="adt-acr").territorio_id
rubrica = BudgetRubrica.objects.get(slug="locacao-veiculo")

def limpar():
    demandas = Demand.objects.filter(titulo__startswith=P)
    ApprovalStep.objects.filter(demanda__in=demandas).delete()
    pools = BudgetAllocation.objects.filter(
        nivel="territorial", territorio_id=territorio_id, rubrica=rubrica, valor_alocado=POOL,
    )
    BudgetTransaction.objects.filter(allocation__in=pools).delete()
    demandas.delete()
    Activity.objects.filter(titulo__startswith=P).delete()
    DemandIndividualLimit.objects.filter(solicitante=adt, rubrica=rubrica).delete()
    pools.delete()
`;

const SETUP_SCRIPT = `${COMUM}
import json
from datetime import timedelta
from django.utils import timezone
from apps.core.models import Municipality
from apps.sgp.models.workplan import WorkPlanAcao
from apps.sgd.services import demand as ds, approval as ap

limpar()
articulador = U.objects.get(email="helio.fontenele@demo.pdhc.local")
ugp = U.objects.get(email="beatriz.nogueira@demo.pdhc.local")

# A Meta vem da primeira Ação do PT, não de um id fixo: ids mudam a cada reseed.
acao = WorkPlanAcao.objects.order_by("pk").first()
META_ID = acao.meta_id
BudgetAllocation.objects.create(
    meta_id=META_ID, rubrica=rubrica, nivel="territorial", territorio_id=territorio_id, valor_alocado=POOL,
)
DemandIndividualLimit.objects.create(solicitante=adt, rubrica=rubrica, valor_limite=Decimal("10000"))

municipio = Municipality.objects.filter(territory_id=territorio_id).order_by("nome").first()
quando = timezone.now() + timedelta(days=20)
atividade = Activity.objects.create(
    titulo=f"{P} Intercâmbio regional", tipo_atividade="intercambio", acao=acao, municipio=municipio,
    forma_atuacao="realizacao", ambito="territorial", tecnico_responsavel=adt,
    data_inicio=quando, data_fim=quando, status="agendado", criado_por=adt,
    descricao_narrativa="Criada pela fixture E2E da issue 296.",
)
CAMPOS = {
    "tipo_veiculo": "van", "data_hora_retirada": "2026-11-10T08:00",
    "data_hora_devolucao": "2026-11-11T18:00", "destino_rota": "Caicó → Mossoró",
    "estimativa_km": 280, "motorista_incluso": True, "combustivel_incluso": True,
    "numero_passageiros": 12,
}

def submetida(titulo):
    d = ds.criar_demanda(titulo=f"{P} {titulo}", activity=atividade, justificativa="", solicitante=adt)
    s = ds.adicionar_solicitacao(d, tipo="veiculo", campos_json=CAMPOS, valor_estimado=Decimal("1200"))
    ds.submeter_demanda(d, usuario=adt)
    return d, s

pre, _ = submetida("Van para o intercâmbio")
dev, _ = submetida("Van sem roteiro definido")
aut, aut_s = submetida("Van da comitiva")
ap.pre_autorizar(aut, responsavel=articulador)
rec, _ = submetida("Van em duplicidade")
ap.pre_autorizar(rec, responsavel=articulador)
atd, _ = submetida("Van do retorno")
ap.pre_autorizar(atd, responsavel=articulador)
ap.autorizar(atd, responsavel=ugp)

ref = lambda d: {"id": d.pk, "titulo": d.titulo}
print("${MARCADOR}_SETUP " + json.dumps({
    "preAutorizar": ref(pre), "devolver": ref(dev),
    "autorizar": {**ref(aut), "solicitacaoId": aut_s.pk},
    "recusar": ref(rec), "atender": ref(atd),
}))
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

export function criarPainelDemandasFixture(): PainelDemandasFixture {
  const saida = djangoShellComoDono(SETUP_SCRIPT);
  const linha = saida
    .split("\n")
    .map((l) => l.trim())
    .find((l) => l.startsWith(`${MARCADOR}_SETUP `));
  if (!linha) {
    throw new Error(`Fixture do painel de demandas não confirmou o setup:\n${saida}`);
  }
  return JSON.parse(linha.slice(`${MARCADOR}_SETUP `.length)) as PainelDemandasFixture;
}

export function removerPainelDemandasFixture(): void {
  djangoShellComoDono(TEARDOWN_SCRIPT);
}
